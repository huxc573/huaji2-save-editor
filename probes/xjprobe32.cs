// XJProbe32.cs —— 32 位探针宿主：加载 System\main.dll，dump 解壳后的内存镜像。
// 编译（x86）：
//   C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /platform:x86 /out:xjprobe32.exe xjprobe32.cs
//
// 用法：
//   xjprobe32.exe dump <main.dll 路径> <输出 bin> [dump 字节数]
//   xjprobe32.exe exports <main.dll 路径>
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

internal static class XJProbe32
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr LoadLibraryW(string path);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr GetProcAddress(IntPtr h, string name);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetModuleHandleW(string name);

    private const uint LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008;

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr LoadLibraryExW(string path, IntPtr file, uint flags);

    private static readonly string[] Names = new string[]
    {
        "qqeat", "init", "init_key", "dispose_key",
        "encryption_file", "decryption_file", "encryption_buff", "decryption_buff",
        "get_md5", "init_debug", "get_hard_disk_character", "shield",
        "net_wrong_count", "read", "readFile", "file_enum", "utf8_to_ansi",
        "get_fsp", "find_fsp", "delete_file", "delete_dir", "dir_count",
        "http_request", "http_bytes", "http_upload", "get_qq", "get_clipboard",
        "copy", "copy_img", "copy_text", "select_file", "screen_capture",
        "get_ttf_name", "call_input", "seek", "test"
    };

    private static int Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.Error.WriteLine("usage: xjprobe32 dump|exports <dll> [out.bin] [size]");
            return 2;
        }
        string mode = args[0];
        string dll = Path.GetFullPath(args[1]);
        if (!File.Exists(dll))
        {
            Console.Error.WriteLine("missing dll: " + dll);
            return 2;
        }

        IntPtr h = LoadLibraryExW(dll, IntPtr.Zero, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (h == IntPtr.Zero)
        {
            Console.Error.WriteLine("LoadLibraryEx failed: " + Marshal.GetLastWin32Error());
            return 3;
        }
        Console.WriteLine("[OK] loaded at 0x" + h.ToInt64().ToString("X8"));

        if (mode == "exports")
        {
            foreach (string n in Names)
            {
                IntPtr p = GetProcAddress(h, n);
                Console.WriteLine("  " + n.PadRight(26) + (p == IntPtr.Zero ? "<none>" :
                    "0x" + p.ToInt64().ToString("X8") + "  (rva 0x" +
                    (p.ToInt64() - h.ToInt64()).ToString("X6") + ")"));
            }
            return 0;
        }

        if (mode == "dump")
        {
            int size = args.Length > 3 ? ParseInt(args[3]) : 0x140000;
            string outPath = Path.GetFullPath(args[2]);
            byte[] buf = new byte[size];
            IntPtr got;
            unsafeRead(h, buf, size, out got);
            File.WriteAllBytes(outPath, buf);
            Console.WriteLine("[OK] dumped " + size + " bytes -> " + outPath);

            // 顺便把内存里的 PE 头几个关键字段打出来
            uint e_lfanew = BitConverter.ToUInt32(buf, 0x3C);
            if (buf[e_lfanew] == (byte)'P' && buf[e_lfanew + 1] == (byte)'E')
            {
                IntPtr ep = (IntPtr)(h.ToInt64() + (long)BitConverter.ToUInt32(buf, (int)e_lfanew + 0x28));
                Console.WriteLine("  in-memory EntryPoint = 0x" + ep.ToInt64().ToString("X8"));
                ushort nsec = BitConverter.ToUInt16(buf, (int)e_lfanew + 6);
                int optSize = BitConverter.ToUInt16(buf, (int)e_lfanew + 20);
                int secOff = (int)e_lfanew + 24 + optSize;
                Console.WriteLine("  sections = " + nsec);
                for (int i = 0; i < nsec; i++)
                {
                    int o = secOff + i * 40;
                    string nm = Encoding.ASCII.GetString(buf, o, 8).TrimEnd('\0');
                    uint vsz = BitConverter.ToUInt32(buf, o + 8);
                    uint vaddr = BitConverter.ToUInt32(buf, o + 12);
                    uint rawsz = BitConverter.ToUInt32(buf, o + 16);
                    uint rawptr = BitConverter.ToUInt32(buf, o + 20);
                    Console.WriteLine(string.Format("    {0,-10} va=0x{1:X6} vsz=0x{2:X6} raw=0x{3:X6}/0x{4:X6}",
                        nm, vaddr, vsz, rawptr, rawsz));
                }
            }
            return 0;
        }

        Console.Error.WriteLine("unknown mode " + mode);
        return 2;
    }

    private static int ParseInt(string s)
    {
        if (s.StartsWith("0x") || s.StartsWith("0X"))
            return Convert.ToInt32(s.Substring(2), 16);
        return int.Parse(s);
    }

    private static void unsafeRead(IntPtr src, byte[] dst, int len, out IntPtr got)
    {
        got = IntPtr.Zero;
        Marshal.Copy(src, dst, 0, len);
    }
}
