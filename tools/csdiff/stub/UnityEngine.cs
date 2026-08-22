// The differential-test engine stub (docs/ROADMAP: the C# diff track).
//
// The game's own assemblies are pure IL — loaded into the modern runtime
// they execute byte-for-byte, provided something resolves the name
// `UnityEngine`. This assembly is that something: the smallest surface
// the methods under test touch, deterministic and headless. It is OUR
// code (nothing of Unity's is copied — the type names are the public
// contract the game assembly links against).
//
// Semantics kept honest:
// - Object equality: the real engine compares native handles; for the
//   uninitialized objects the runner fabricates, reference identity is
//   the same relation (no destroyed-object limbo exists here).
// - PlayerPrefs: an in-memory store the runner snapshots per case.
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public string name = "";
        public static bool operator ==(Object a, Object b)
            => ReferenceEquals(a, b);
        public static bool operator !=(Object a, Object b)
            => !ReferenceEquals(a, b);
        public override bool Equals(object o) => ReferenceEquals(this, o);
        public override int GetHashCode()
            => System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(this);
        public static implicit operator bool(Object o) => o is not null;
    }

    public class Component : Object { }
    public class Behaviour : Component { }
    public class MonoBehaviour : Behaviour { }
    public class GameObject : Object { }
    public class Transform : Component { }

    public struct Vector2
    {
        public float x, y;
        public Vector2(float x, float y) { this.x = x; this.y = y; }
    }

    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z)
        { this.x = x; this.y = y; this.z = z; }
    }

    public struct Vector4
    {
        public float x, y, z, w;
    }

    public struct Quaternion
    {
        public float x, y, z, w;
    }

    public struct Color
    {
        public float r, g, b, a;
    }

    public struct Rect
    {
        public float x, y, width, height;
    }

    public static class PlayerPrefs
    {
        public static readonly Dictionary<string, object> Store = new();
        // real overloads, not default parameters: the game was compiled
        // against both arities, so both signatures must exist
        public static void SetInt(string k, int v) => Store[k] = v;
        public static int GetInt(string k) => GetInt(k, 0);
        public static int GetInt(string k, int d)
            => Store.TryGetValue(k, out var v) ? (int)v : d;
        public static void SetFloat(string k, float v) => Store[k] = v;
        public static float GetFloat(string k) => GetFloat(k, 0f);
        public static float GetFloat(string k, float d)
            => Store.TryGetValue(k, out var v) ? (float)v : d;
        public static void SetString(string k, string v) => Store[k] = v;
        public static string GetString(string k) => GetString(k, "");
        public static string GetString(string k, string d)
            => Store.TryGetValue(k, out var v) ? (string)v : d;
        public static bool HasKey(string k) => Store.ContainsKey(k);
        public static void DeleteKey(string k) => Store.Remove(k);
        public static void DeleteAll() => Store.Clear();
        public static void Save() { }
    }

    public static class Debug
    {
        public static void Log(object m) { }
        public static void LogWarning(object m) { }
        public static void LogError(object m) { }
        public static void LogException(System.Exception e) { }
    }

    public static class Application
    {
        // Application.loadedLevel: the scene index GetLevelIndex reads;
        // each case sets it before the call (a property — the game links
        // against get_loadedLevel)
        public static int loadedLevel { get; set; }
    }

    public static class Time
    {
        public static float deltaTime = 1f / 60f;
        public static float time = 0f;
        public static float timeScale = 1f;
    }

    public static class Mathf
    {
        public static float Clamp(float v, float lo, float hi)
            => v < lo ? lo : (v > hi ? hi : v);
        public static int Clamp(int v, int lo, int hi)
            => v < lo ? lo : (v > hi ? hi : v);
        public static float Min(float a, float b) => a < b ? a : b;
        public static float Max(float a, float b) => a > b ? a : b;
        public static int FloorToInt(float v)
            => (int)System.Math.Floor(v);
        public static int CeilToInt(float v)
            => (int)System.Math.Ceiling(v);
        public static int RoundToInt(float v)
            => (int)System.Math.Round(v, System.MidpointRounding.ToEven);
        public static float Abs(float v) => v < 0 ? -v : v;
    }
}
