// The differential-test runner (track C of the bug hunt): load the
// game's own Assembly-CSharp.dll from the user's data, fabricate the
// objects a method under test needs, execute the ORIGINAL bytecode and
// dump the resulting state as JSON for tests/run_csdiff.py to diff
// against the port.
//
//   dotnet run -- <ManagedDir> <cases.json>
//
// The assembly's `UnityEngine` reference resolves to our stub (built
// alongside); every other dependency resolves from ManagedDir, except
// the framework libraries, which unify onto the modern runtime.
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.Loader;
using System.Text.Json;

class Runner
{
    static Assembly game = null!;

    static int Main(string[] args)
    {
        if (args.Length != 2)
        {
            Console.Error.WriteLine("usage: runner <ManagedDir> <cases.json>");
            return 2;
        }
        string managed = args[0];
        // the stub is in our own deps — touching a type loads it
        _ = typeof(UnityEngine.PlayerPrefs);
        AssemblyLoadContext.Default.Resolving += (ctx, name) =>
        {
            if (name.Name != null && name.Name.StartsWith("UnityEngine"))
                return typeof(UnityEngine.Object).Assembly;
            string p = Path.Combine(managed, name.Name + ".dll");
            return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
        };
        game = AssemblyLoadContext.Default.LoadFromAssemblyPath(
            Path.GetFullPath(Path.Combine(managed, "Assembly-CSharp.dll")));

        var cases = JsonSerializer.Deserialize<List<JsonElement>>(
            File.ReadAllText(args[1]))!;
        var results = new List<object>();
        foreach (var c in cases)
            results.Add(RunCase(c));
        Console.WriteLine(JsonSerializer.Serialize(results,
            new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }

    static object Fab(string typeName)
        => RuntimeHelpers.GetUninitializedObject(game.GetType(typeName, true)!);

    static void SetField(object obj, string name, JsonElement v)
    {
        var t = obj.GetType();
        FieldInfo? f = null;
        for (var cur = t; cur != null && f == null; cur = cur.BaseType)
            f = cur.GetField(name, BindingFlags.Instance | BindingFlags.Public
                                   | BindingFlags.NonPublic);
        if (f == null)
            throw new MissingFieldException(t.FullName, name);
        f.SetValue(obj, FromJson(v, f.FieldType));
    }

    static object? FromJson(JsonElement v, Type t)
    {
        if (t == typeof(int)) return v.GetInt32();
        if (t == typeof(bool)) return v.GetBoolean();
        if (t == typeof(float)) return v.GetSingle();
        if (t == typeof(string)) return v.GetString();
        if (t.IsEnum) return Enum.ToObject(t, v.GetInt32());
        throw new NotSupportedException(t.FullName);
    }

    static object? GetField(object obj, string name)
    {
        for (var cur = obj.GetType(); cur != null; cur = cur.BaseType)
        {
            var f = cur.GetField(name, BindingFlags.Instance
                | BindingFlags.Public | BindingFlags.NonPublic);
            if (f != null) return f.GetValue(obj);
        }
        throw new MissingFieldException(obj.GetType().FullName, name);
    }

    static void SetStatic(string typeName, string field, object? value)
    {
        var t = game.GetType(typeName, true)!;
        var f = t.GetField(field, BindingFlags.Static | BindingFlags.Public
                                  | BindingFlags.NonPublic)
                ?? throw new MissingFieldException(typeName, field);
        f.SetValue(null, value);
    }

    static object RunCase(JsonElement c)
    {
        UnityEngine.PlayerPrefs.DeleteAll();
        UnityEngine.Application.loadedLevel =
            c.TryGetProperty("loadedLevel", out var ll) ? ll.GetInt32() : 5;

        // BuildSettings singleton: its own class constructor creates the
        // readonly `instance`; only the app-name statics need setting
        var appName = Enum.ToObject(game.GetType("NFH.AppLauncher.AppName", true)!,
            c.TryGetProperty("appName", out var an) ? an.GetInt32() : 0);
        SetStatic("BuildSettings", "CurrentAppName", appName);

        var gi = Fab("GameInfo");
        var woody = Fab("Woody");
        foreach (var kv in c.GetProperty("woody").EnumerateObject())
            SetField(woody, kv.Name, kv.Value);
        SetField2(gi, "Woody", woody);
        if (c.TryGetProperty("rott", out var rj)
            && rj.ValueKind == JsonValueKind.Object)
        {
            var rott = Fab("Rottweiler");
            foreach (var kv in rj.EnumerateObject())
                SetField(rott, kv.Name, kv.Value);
            SetField2(gi, "Rottweiler", rott);
        }
        foreach (var kv in c.GetProperty("gameinfo").EnumerateObject())
            SetField(gi, kv.Name, kv.Value);

        string? error = null;
        try
        {
            gi.GetType().GetMethod("CalculateScore",
                BindingFlags.Instance | BindingFlags.Public)!
                .Invoke(gi, null);
        }
        catch (TargetInvocationException e)
        {
            error = e.InnerException?.ToString() ?? e.ToString();
        }

        var prefs = new SortedDictionary<string, object>(
            UnityEngine.PlayerPrefs.Store);
        return new Dictionary<string, object?>
        {
            ["name"] = c.GetProperty("name").GetString(),
            ["FinalViewerRating"] = GetField(gi, "FinalViewerRating"),
            ["FinalTrickScore"] = GetField(gi, "FinalTrickScore"),
            ["FinalCompoundTrickScore"] = GetField(gi, "FinalCompoundTrickScore"),
            ["CompoundTrickScore"] = GetField(gi, "CompoundTrickScore"),
            ["Perfect"] = GetField(gi, "Perfect"),
            ["Rating"] = GetField(gi, "Rating"),
            ["TrickRatio"] = GetField(gi, "TrickRatio"),
            ["ViewerRating"] = GetField(gi, "ViewerRating"),
            ["prefs"] = prefs,
            ["error"] = error,
        };
    }

    // set a field holding a game-typed object (no JSON conversion)
    static void SetField2(object obj, string name, object value)
    {
        for (var cur = obj.GetType(); cur != null; cur = cur.BaseType)
        {
            var f = cur.GetField(name, BindingFlags.Instance
                | BindingFlags.Public | BindingFlags.NonPublic);
            if (f != null) { f.SetValue(obj, value); return; }
        }
        throw new MissingFieldException(obj.GetType().FullName, name);
    }
}
