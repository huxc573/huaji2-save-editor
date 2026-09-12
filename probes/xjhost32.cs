// XJHost32.cs —— 32 位宿主：加载 System\main.dll 并按脚本调用其导出。
//
// 编译：
//   C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /platform:x86 /out:xjhost32.exe xjhost32.cs
//
// 用法：
//   xjhost32.exe exports <dll>
//   xjhost32.exe dump    <dll> <out.bin> [size]
//   xjhost32.exe script  <dll> <script.txt>
//
// 脚本每行（# 开头忽略），用【分号】分隔，避免路径里的空格：
//   <func>;[arg];[arg]...
//   arg 形式： s文本（ANSI 字符串指针） / i十进制 / x十六进制 / e（NULL）
//             b文件路径（读成堆缓冲，指针传入）
//             o文件路径,长度（传入堆缓冲指针，调用后把该长度写回文件）
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

internal static class XJHost32
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr LoadLibraryExW(string path, IntPtr file, uint flags);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr GetProcAddress(IntPtr h, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetDllDirectoryW(string path);

    private const uint LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008;

    private delegate int D0();
    private delegate int D1(IntPtr a);
    private delegate int D2(IntPtr a, IntPtr b);
    private delegate int D3(IntPtr a, IntPtr b, IntPtr c);
    private delegate int D4(IntPtr a, IntPtr b, IntPtr c, IntPtr d);

    private static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.ASCII;
        if (args.Length < 2) { Console.WriteLine("usage: xjhost32 exports|dump|script <dll> ..."); return 2; }
        string mode = args[0];
        string dll = Path.GetFullPath(args[1]);
        if (!File.Exists(dll)) { Console.WriteLine("[ERR] no dll " + dll); return 2; }
        SetDllDirectoryW(Path.GetDirectoryName(dll));
        IntPtr h = LoadLibraryExW(dll, IntPtr.Zero, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (h == IntPtr.Zero) { Console.WriteLine("[ERR] LoadLibrary " + Marshal.GetLastWin32Error()); return 3; }
        Console.WriteLine("[OK] base=0x" + h.ToInt64().ToString("X8"));

        if (mode == "exports")
        {
            foreach (string n in new[] { "qqeat", "init", "init_key", "dispose_key",
                "encryption_file", "decryption_file", "encryption_buff", "decryption_buff",
                "get_md5", "init_debug", "read", "readFile" })
            {
                IntPtr p = GetProcAddress(h, n);
                Console.WriteLine("  " + n.PadRight(20) + (p == IntPtr.Zero ? "<none>" :
                    "0x" + p.ToInt64().ToString("X8")));
            }
            return 0;
        }
        if (mode == "dump")
        {
            int size = args.Length > 3 ? ParseInt(args[3]) : 0x140000;
            byte[] buf = new byte[size];
            Marshal.Copy(h, buf, 0, size);
            File.WriteAllBytes(Path.GetFullPath(args[2]), buf);
            Console.WriteLine("[OK] dumped " + size);
            return 0;
        }
        if (mode == "script") return Script(h, args[2]);
        if (mode == "probe")
        {
            // 在后台线程跑 <func>（例如 qqeat），等 N 毫秒后主线程继续跑脚本
            string fn = args[2];
            int waitMs = args.Length > 3 ? int.Parse(args[3]) : 3000;
            IntPtr fp = GetProcAddress(h, fn);
            Console.WriteLine("[probe] " + fn + " @0x" + fp.ToInt64().ToString("X8") +
                " 等待 " + waitMs + "ms");
            if (fp != IntPtr.Zero)
            {
                System.Threading.Thread t = new System.Threading.Thread(() =>
                {
                    try
                    {
                        ((D0)Marshal.GetDelegateForFunctionPointer(fp, typeof(D0)))();
                        Console.WriteLine("[probe] " + fn + " 已返回");
                    }
                    catch (Exception e) { Console.WriteLine("[probe] " + fn + " 异常 " + e.Message); }
                });
                t.IsBackground = true;
                t.Start();
            }
            System.Threading.Thread.Sleep(waitMs);
            return args.Length > 4 ? Script(h, args[4]) : 0;
        }
        Console.WriteLine("[ERR] unknown mode");
        return 2;
    }

    // ------------------------------------------------------------------ script
    private static int Script(IntPtr h, string scriptPath)
    {
        string[] lines = File.ReadAllLines(scriptPath, Encoding.UTF8);
        foreach (string raw in lines)
        {
            string line = raw.Trim();
            if (line.Length == 0 || line[0] == '#') continue;
            string[] tk = line.Split(';');
            for (int i = 0; i < tk.Length; i++) tk[i] = tk[i].Trim();
            Console.WriteLine(">> " + line);
            IntPtr fp = GetProcAddress(h, tk[0]);
            if (fp == IntPtr.Zero) { Console.WriteLine("   [ERR] no export " + tk[0]); continue; }
            List<IntPtr> vals = new List<IntPtr>();
            for (int i = 1; i < tk.Length; i++)
            {
                string t = tk[i];
                if (t == "e") { vals.Add(IntPtr.Zero); continue; }
                switch (t[0])
                {
                    case 's': vals.Add(Utf8Ptr(t.Substring(1))); break;
                    case 'i': vals.Add(new IntPtr(int.Parse(t.Substring(1)))); break;
                    case 'x': vals.Add(new IntPtr(Convert.ToInt32(t.Substring(1), 16))); break;
                    case 'b':
                        {
                            byte[] d = File.ReadAllBytes(t.Substring(1));
                            IntPtr p = Marshal.AllocHGlobal(d.Length + 16);
                            Marshal.Copy(d, 0, p, d.Length);
                            vals.Add(p);
                            break;
                        }
                    case 'o':
                        {
                            string[] parts = t.Substring(1).Split(',');
                            int len = parts.Length > 1 ? int.Parse(parts[1]) : 0;
                            IntPtr p = Marshal.AllocHGlobal(Math.Max(len, 1) + 16);
                            for (int k = 0; k < Math.Max(len, 1) + 16; k++) Marshal.WriteByte(p, k, 0);
                            vals.Add(p);
                            break;
                        }
                    default: Console.WriteLine("   [ERR] bad arg " + t); break;
                }
            }
            try
            {
                int r = Dispatch(fp, vals);
                Console.WriteLine("   ret=" + r + " (0x" + r.ToString("X8") + ")");
                int vi = 0;
                for (int i = 1; i < tk.Length; i++)
                {
                    if (tk[i][0] == 'o')
                    {
                        string[] parts = tk[i].Substring(1).Split(',');
                        int len = parts.Length > 1 ? int.Parse(parts[1]) : 0;
                        if (len > 0)
                        {
                            byte[] d = new byte[len];
                            Marshal.Copy(vals[vi], d, 0, len);
                            File.WriteAllBytes(parts[0], d);
                            Console.WriteLine("   wrote " + parts[0] + " " + len + "B head=" + Head(d, 8));
                        }
                    }
                    else if (tk[i][0] == 'b')
                    {
                        byte[] d = File.ReadAllBytes(tk[i].Substring(1));
                        if (d.Length > 0)
                        {
                            int n = Math.Min(d.Length, 16);
                            byte[] now = new byte[n];
                            Marshal.Copy(vals[vi], now, 0, n);
                            Console.WriteLine("   (in-buf now) " + Head(now, n));
                        }
                    }
                    vi++;
                }
            }
            catch (Exception e) { Console.WriteLine("   [EXC] " + e.Message); }
        }
        return 0;
    }

    /// <summary>把托管字符串按 UTF-8 写入非托管内存（main.dll 内部再转 GBK）。</summary>
    private static IntPtr Utf8Ptr(string s)
    {
        byte[] b = Encoding.UTF8.GetBytes(s);
        IntPtr p = Marshal.AllocHGlobal(b.Length + 1);
        Marshal.Copy(b, 0, p, b.Length);
        Marshal.WriteByte(p, b.Length, 0);
        return p;
    }

    private static string Head(byte[] d, int n)
    {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < Math.Min(n, d.Length); i++) sb.Append(d[i].ToString("X2") + " ");
        return sb.ToString().Trim();
    }

    private static int Dispatch(IntPtr fp, List<IntPtr> v)
    {
        switch (v.Count)
        {
            case 0: return ((D0)Marshal.GetDelegateForFunctionPointer(fp, typeof(D0)))();
            case 1: return ((D1)Marshal.GetDelegateForFunctionPointer(fp, typeof(D1)))(v[0]);
            case 2: return ((D2)Marshal.GetDelegateForFunctionPointer(fp, typeof(D2)))(v[0], v[1]);
            case 3: return ((D3)Marshal.GetDelegateForFunctionPointer(fp, typeof(D3)))(v[0], v[1], v[2]);
            case 4: return ((D4)Marshal.GetDelegateForFunctionPointer(fp, typeof(D4)))(v[0], v[1], v[2], v[3]);
            default: throw new Exception("too many args");
        }
    }

    private static int ParseInt(string s)
    {
        if (s.StartsWith("0x") || s.StartsWith("0X")) return Convert.ToInt32(s.Substring(2), 16);
        return int.Parse(s);
    }
}
