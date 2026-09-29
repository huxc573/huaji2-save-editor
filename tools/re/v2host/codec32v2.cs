// XJCodec32v2 —— 在 v1 基础上增加启动初始化（qqeat）支持。
// 变化点：LoadDll 之后先调 qqeat(0)（V2.2 启动脚本的第一步），再按模式分发。
// 其余逻辑与 codec32.cs 完全一致。
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

internal static class XJCodec32v2
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr LoadLibraryExW(string path, IntPtr file, uint flags);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr GetProcAddress(IntPtr h, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetDllDirectoryW(string path);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool VirtualProtect(IntPtr addr, IntPtr size, uint newProtect,
                                              out uint oldProtect);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern UIntPtr VirtualQuery(IntPtr addr, out MBI buffer, UIntPtr length);

    private struct MBI
    {
        public IntPtr BaseAddress;
        public IntPtr AllocationBase;
        public uint AllocationProtect;
        public IntPtr RegionSize;
        public uint State;
        public uint Protect;
        public uint Type;
    }

    private const uint MEM_COMMIT = 0x1000;

    /// <summary>从模块基址开始，把所有已提交内存拼成镜像 dump（未提交区填 0）。</summary>
    private static int ParseInt(string s)
    {
        s = s.Trim();
        if (s.StartsWith("0x") || s.StartsWith("0X"))
            return Convert.ToInt32(s.Substring(2), 16);
        return int.Parse(s);
    }

    private static int DumpImage(IntPtr h, string outPath, long span)
    {
        byte[] img = new byte[span];
        long start = h.ToInt64();
        long a = start;
        long end = start + span;
        long total = 0;
        while (a < end)
        {
            MBI mbi;
            if (VirtualQuery((IntPtr)a, out mbi, (UIntPtr)Marshal.SizeOf(typeof(MBI))) == UIntPtr.Zero)
                break;
            long rsize = mbi.RegionSize.ToInt64();
            if (rsize <= 0) break;
            if (mbi.State == MEM_COMMIT)
            {
                long n = Math.Min(rsize, end - a);
                if (n > int.MaxValue) n = int.MaxValue;
                byte[] part = new byte[n];
                Marshal.Copy((IntPtr)a, part, 0, (int)n);
                Array.Copy(part, 0, img, a - start, n);
                total += n;
            }
            a += rsize;
        }
        File.WriteAllBytes(outPath, img);
        Console.WriteLine("[INFO] committed=" + total + " span=" + span);
        Console.WriteLine("[OK] dumped " + outPath);
        return 0;
    }

    private const uint PAGE_EXECUTE_READWRITE = 0x40;
    private const uint LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008;

    private delegate int D3(IntPtr a, IntPtr b, IntPtr c);
    private delegate int D4(IntPtr a, IntPtr b, IntPtr c, IntPtr d);
    private delegate IntPtr D0();
    private delegate int D1(int a);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr GetModuleHandleA(string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool WriteProcessMemory(IntPtr h, IntPtr addr, byte[] buf,
                                                  UIntPtr size, out UIntPtr written);

    /// <summary>把 ExitProcess / TerminateProcess 打成空操作（防壳环境自检自杀）。</summary>
    private static void HookAntiExit()
    {
        IntPtr k32 = GetModuleHandleA("kernel32.dll");
        PatchRet(k32, "ExitProcess", 0xC3, 0);
        PatchRet(k32, "TerminateProcess", 0xC2, 8);
        IntPtr nt = GetModuleHandleA("ntdll.dll");
        if (nt != IntPtr.Zero) PatchRet(nt, "NtTerminateProcess", 0xC2, 8);
    }

    private static void PatchRet(IntPtr mod, string func, byte op, int imm)
    {
        IntPtr p = GetProcAddress(mod, func);
        if (p == IntPtr.Zero) return;
        byte[] code;
        if (op == 0xC3) code = new byte[] { 0xC3 };
        else code = new byte[] { op, (byte)(imm & 0xFF), (byte)((imm >> 8) & 0xFF) };
        uint old;
        if (!VirtualProtect(p, (IntPtr)code.Length, PAGE_EXECUTE_READWRITE, out old))
            return;
        UIntPtr w;
        WriteProcessMemory((IntPtr)(-1), p, code, (UIntPtr)code.Length, out w);
        VirtualProtect(p, (IntPtr)code.Length, old, out old);
        Console.WriteLine("[INFO] hooked " + func);
    }

    private static int Call4(IntPtr fn, string a, string b, string c, IntPtr d)
    {
        IntPtr pa = Utf8(a), pb = Utf8(b), pc = Utf8(c);
        try
        {
            D4 f = (D4)Marshal.GetDelegateForFunctionPointer(fn, typeof(D4));
            return f(pa, pb, pc, d);
        }
        finally
        {
            Marshal.FreeHGlobal(pa);
            Marshal.FreeHGlobal(pb);
            Marshal.FreeHGlobal(pc);
        }
    }

    private static IntPtr LoadDll(string dll)
    {
        if (!File.Exists(dll)) throw new IOException("cannot find " + dll);
        SetDllDirectoryW(Path.GetDirectoryName(dll));
        IntPtr h = LoadLibraryExW(dll, IntPtr.Zero, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (h == IntPtr.Zero)
            throw new IOException("LoadLibrary failed (Win32 err="
                + Marshal.GetLastWin32Error() + "): " + dll);
        return h;
    }

    /// <summary>调用 qqeat(0)（存在才调）。返回是否调用成功。</summary>
    private static bool InitSeq(IntPtr h)
    {
        IntPtr q = GetProcAddress(h, "qqeat");
        if (q == IntPtr.Zero)
        {
            Console.WriteLine("[INFO] qqeat absent");
            return false;
        }
        try
        {
            D1 f = (D1)Marshal.GetDelegateForFunctionPointer(q, typeof(D1));
            int r = f(0);
            Console.WriteLine("[INFO] qqeat(0) ret=" + r);
            return true;
        }
        catch (Exception e)
        {
            Console.WriteLine("[WARN] qqeat(0) threw: " + e.GetType().Name);
            return false;
        }
    }

    private static IntPtr Utf8(string s)
    {
        byte[] b = Encoding.UTF8.GetBytes(s ?? "");
        IntPtr p = Marshal.AllocHGlobal(b.Length + 1);
        Marshal.Copy(b, 0, p, b.Length);
        Marshal.WriteByte(p, b.Length, 0);
        return p;
    }

    private static int Call3(IntPtr fn, string a, string b, string c)
    {
        IntPtr pa = Utf8(a), pb = Utf8(b), pc = Utf8(c);
        try
        {
            D3 f = (D3)Marshal.GetDelegateForFunctionPointer(fn, typeof(D3));
            return f(pa, pb, pc);
        }
        finally
        {
            Marshal.FreeHGlobal(pa);
            Marshal.FreeHGlobal(pb);
            Marshal.FreeHGlobal(pc);
        }
    }

    private static IntPtr Export(IntPtr h, string name)
    {
        IntPtr p = GetProcAddress(h, name);
        if (p == IntPtr.Zero) throw new IOException("no export: " + name);
        return p;
    }

    private static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.ASCII;
        try
        {
            if (args.Length < 2) { Console.WriteLine("[ERR] args"); return 2; }
            string mode = args[0].ToLowerInvariant();
            string dll = Path.GetFullPath(args[1]);
            IntPtr h = LoadDll(dll);
            Console.WriteLine("[INFO] base=0x" + h.ToInt64().ToString("X8"));

            if (mode == "probe" || mode == "decrypt" || mode == "encrypt")
            {
                HookAntiExit();
                if (Environment.GetEnvironmentVariable("XJ_QQEAT") == "1") InitSeq(h);
            }

            if (mode == "rawinfo" || mode == "info")
            {
                foreach (string n in new[] { "init", "init_key", "dispose_key",
                    "qqeat", "encryption_file", "decryption_file",
                    "encryption_buff", "decryption_buff", "get_md5",
                    "file_get_size", "run", "sys01", "get_result" })
                {
                    IntPtr p = GetProcAddress(h, n);
                    Console.WriteLine("[INFO] " + n.PadRight(18) +
                        (p == IntPtr.Zero ? "<absent>" : "0x" + p.ToInt64().ToString("X8")));
                }
                return 0;
            }

            if (mode == "dump2")
            {
                long span = args.Length > 3 ? ParseInt(args[3]) : 0x1400000;
                return DumpImage(h, Path.GetFullPath(args[2]), span);
            }

            if (mode == "machine")
            {
                IntPtr fn = GetProcAddress(h, "get_hard_disk_character");
                if (fn == IntPtr.Zero) { Console.WriteLine("[ERR] no export"); return 3; }
                D0 f = (D0)Marshal.GetDelegateForFunctionPointer(fn, typeof(D0));
                IntPtr sp = f();
                if (sp == IntPtr.Zero) { Console.WriteLine("[ERR] null"); return 4; }
                Console.WriteLine("[INFO] id=" + Marshal.PtrToStringAnsi(sp));
                Console.WriteLine("[OK] machine id");
                return 0;
            }

            if (mode == "probe")
            {
                if (args.Length < 4) { Console.WriteLine("[ERR] args"); return 2; }
                string t = Path.GetFullPath(args[2]);
                string o = t + ".probe_out";
                if (File.Exists(o)) File.Delete(o);
                IntPtr d4;
                string a4 = args.Length > 4 ? args[4] : "0";
                if (a4.StartsWith("s:"))
                    d4 = Utf8(a4.Substring(2));          // 第 4 参按字符串传
                else
                    d4 = (IntPtr)ParseInt(a4);
                int r = Call4(Export(h, "decryption_file"), t, o, args[3], d4);
                Console.WriteLine("[INFO] ret=" + r);
                string dpath = Environment.GetEnvironmentVariable("XJ_DUMP");
                if (dpath != null) DumpImage(h, dpath, 0x1400000);
                long n = File.Exists(o) ? new FileInfo(o).Length : -1;
                Console.WriteLine("[INFO] ret=" + r + " outsize=" + n);
                if (n > 0)
                {
                    byte[] hd = new byte[Math.Min(8, (int)n)];
                    using (FileStream fs = File.OpenRead(o)) fs.Read(hd, 0, hd.Length);
                    Console.WriteLine("[INFO] head=" + BitConverter.ToString(hd).Replace("-", " "));
                    Console.WriteLine("[OK] hit");
                    return 0;
                }
                Console.WriteLine("[ERR] miss");
                return 4;
            }

            if (mode == "decrypt" || mode == "encrypt")
            {
                if (args.Length < 4) { Console.WriteLine("[ERR] args"); return 2; }
                string src = Path.GetFullPath(args[2]);
                string dst = Path.GetFullPath(args[3]);
                string key = args.Length > 4 ? args[4] : "";
                if (!File.Exists(src)) { Console.WriteLine("[ERR] no input"); return 3; }
                if (File.Exists(dst)) File.Delete(dst);
                string fn = mode == "decrypt" ? "decryption_file" : "encryption_file";
                IntPtr d4 = (IntPtr)(args.Length > 5 ? ParseInt(args[5]) : 0);
                int r = Call4(Export(h, fn), src, dst, key, d4);
                long outLen = File.Exists(dst) ? new FileInfo(dst).Length : -1;
                Console.WriteLine("[INFO] ret=" + r);
                Console.WriteLine("[INFO] outsize=" + outLen);
                if (outLen > 0)
                {
                    byte[] head = new byte[Math.Min(8, (int)outLen)];
                    using (FileStream fs = File.OpenRead(dst))
                        fs.Read(head, 0, head.Length);
                    Console.WriteLine("[INFO] head=" + BitConverter.ToString(head).Replace("-", " "));
                    Console.WriteLine("[OK] " + outLen + " bytes");
                    return 0;
                }
                Console.WriteLine("[ERR] empty output");
                return 4;
            }

            Console.WriteLine("[ERR] unknown mode " + mode);
            return 2;
        }
        catch (Exception e)
        {
            Console.WriteLine("[ERR] " + e.Message);
            return 1;
        }
    }
}
