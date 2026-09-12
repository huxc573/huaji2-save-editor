// XJCodec32.cs —— 《画迹2：缘起凡尘》加密文件编解码宿主（32 位）
//
// 为什么需要它：游戏的加密在 `System\main.dll` 里（MPRESS 加壳的自定义算法），
// 该 DLL 是 32 位的，64 位 Python 无法直接加载，所以用一个 32 位的 .NET 宿主
// 通过 LoadLibrary + GetProcAddress 调用它的 `encryption_file` / `decryption_file`
// 导出，再由 Python 用 subprocess 驱动。
//
// 编译（x86）：
//   C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe /platform:x86 /out:XJCodec32.exe XJCodec32.cs
//
// 用法：
//   XJCodec32.exe info    <main.dll>
//   XJCodec32.exe decrypt <main.dll> <输入文件> <输出文件> [第三参数]
//   XJCodec32.exe encrypt <main.dll> <输入文件> <输出文件> [第三参数]
//   XJCodec32.exe selftest<main.dll>          # 自检：随机数据往返
//
// 约定：字符串参数一律以 **UTF-8** 传入（main.dll 内部自己做 UTF8→GBK 转换，
// 传 ANSI 会导致中文路径打不开文件 —— 这是踩过的坑）。
//
// 输出格式（供 Python 解析）：
//   [OK] ...   [ERR] ...   [INFO] key=value
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

internal static class XJCodec32
{
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr LoadLibraryExW(string path, IntPtr file, uint flags);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Ansi)]
    private static extern IntPtr GetProcAddress(IntPtr h, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetDllDirectoryW(string path);

    private const uint LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008;

    private delegate int D3(IntPtr a, IntPtr b, IntPtr c);

    private static IntPtr LoadDll(string dll)
    {
        if (!File.Exists(dll)) throw new IOException("找不到 " + dll);
        SetDllDirectoryW(Path.GetDirectoryName(dll));
        IntPtr h = LoadLibraryExW(dll, IntPtr.Zero, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (h == IntPtr.Zero)
            throw new IOException("LoadLibrary 失败, win32err=" + Marshal.GetLastWin32Error());
        return h;
    }

    /// <summary>把托管字符串按 UTF-8 写进非托管内存（main.dll 期望 UTF-8）。</summary>
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
        if (p == IntPtr.Zero) throw new IOException("main.dll 没有导出 " + name);
        return p;
    }

    private static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.ASCII;
        try
        {
            if (args.Length < 2) { Console.WriteLine("[ERR] 参数不足"); return 2; }
            string mode = args[0].ToLowerInvariant();
            string dll = Path.GetFullPath(args[1]);
            IntPtr h = LoadDll(dll);
            Console.WriteLine("[INFO] base=0x" + h.ToInt64().ToString("X8"));

            if (mode == "info")
            {
                foreach (string n in new[] { "init", "init_key", "dispose_key",
                    "encryption_file", "decryption_file", "encryption_buff",
                    "decryption_buff", "get_md5", "qqeat" })
                {
                    IntPtr p = GetProcAddress(h, n);
                    Console.WriteLine("[INFO] " + n.PadRight(18) +
                        (p == IntPtr.Zero ? "<缺失>" : "0x" + p.ToInt64().ToString("X8")));
                }
                return 0;
            }

            if (mode == "decrypt" || mode == "encrypt")
            {
                if (args.Length < 4) { Console.WriteLine("[ERR] 参数不足"); return 2; }
                string src = Path.GetFullPath(args[2]);
                string dst = Path.GetFullPath(args[3]);
                string key = args.Length > 4 ? args[4] : "";
                if (!File.Exists(src)) { Console.WriteLine("[ERR] 找不到输入 " + src); return 3; }
                if (File.Exists(dst)) File.Delete(dst);

                string fn = mode == "decrypt" ? "decryption_file" : "encryption_file";
                int r = Call3(Export(h, fn), src, dst, key);
                long outLen = File.Exists(dst) ? new FileInfo(dst).Length : -1;
                Console.WriteLine("[INFO] func=" + fn);
                Console.WriteLine("[INFO] ret=" + r);
                Console.WriteLine("[INFO] outsize=" + outLen);
                if (outLen > 0)
                {
                    byte[] head = new byte[8];
                    using (FileStream fs = File.OpenRead(dst))
                        fs.Read(head, 0, Math.Min(8, (int)Math.Min(8, outLen)));
                    bool marshal = head[0] == 4 && head[1] == 8;
                    Console.WriteLine("[INFO] head=" + BitConverter.ToString(head).Replace("-", " "));
                    Console.WriteLine("[INFO] marshal=" + (marshal ? "yes" : "no"));
                    Console.WriteLine("[OK] " + outLen + " bytes");
                    return 0;
                }
                Console.WriteLine("[ERR] 输出为空（密文不匹配当前密钥状态）");
                return 4;
            }

            if (mode == "selftest")
            {
                string tmp = Path.Combine(Path.GetTempPath(), "xjcodec_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(tmp);
                string p0 = Path.Combine(tmp, "plain.bin");
                string p1 = Path.Combine(tmp, "enc.bin");
                string p2 = Path.Combine(tmp, "back.bin");
                byte[] data = new byte[4096];
                new Random(12345).NextBytes(data);
                // 明文里塞一段长 0，便于肉眼核对 ECB 特征
                for (int i = 1024; i < 2048; i++) data[i] = 0;
                File.WriteAllBytes(p0, data);
                Console.WriteLine("[INFO] 原始 " + data.Length + " 字节");
                Call3(Export(h, "encryption_file"), p0, p1, "");
                Console.WriteLine("[INFO] 加密后 " + new FileInfo(p1).Length + " 字节 (+8)");
                Call3(Export(h, "decryption_file"), p1, p2, "");
                byte[] back = File.ReadAllBytes(p2);
                bool ok = back.Length == data.Length;
                if (ok)
                    for (int i = 0; i < data.Length; i++)
                        if (back[i] != data[i]) { ok = false; break; }
                Console.WriteLine("[INFO] 往返一致=" + (ok ? "yes" : "no"));
                if (ok) { Console.WriteLine("[OK] 自检通过"); return 0; }
                Console.WriteLine("[ERR] 自检失败");
                return 5;
            }

            Console.WriteLine("[ERR] 未知模式 " + mode);
            return 2;
        }
        catch (Exception e)
        {
            Console.WriteLine("[ERR] " + e.Message);
            return 1;
        }
    }
}
