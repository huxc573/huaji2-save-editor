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
//   XJCodec32.exe machine <main.dll>            # 取本机机器码
//   XJCodec32.exe selftest<main.dll>          # 自检：随机数据往返
//
// 约定：字符串参数一律以 **UTF-8** 传入（main.dll 内部自己做 UTF8→GBK 转换，
// 传 ANSI 会导致中文路径打不开文件 —— 这是踩过的坑）。
//
// 输出格式（供 Python 解析）：
//   [OK] ...   [ERR] ...   [INFO] key=value
using System;
using System.Collections.Generic;
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

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool VirtualProtect(IntPtr addr, IntPtr size, uint newProtect,
                                              out uint oldProtect);

    private const uint PAGE_EXECUTE_READWRITE = 0x40;

    private const uint LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008;

    private delegate int D3(IntPtr a, IntPtr b, IntPtr c);

    /// <summary>无参、返回字符串指针的导出（get_hard_disk_character）。</summary>
    private delegate IntPtr D0();

    private static IntPtr LoadDll(string dll)
    {
        if (!File.Exists(dll)) throw new IOException("找不到 " + dll);
        SetDllDirectoryW(Path.GetDirectoryName(dll));
        IntPtr h = LoadLibraryExW(dll, IntPtr.Zero, LOAD_WITH_ALTERED_SEARCH_PATH);
        if (h == IntPtr.Zero)
            throw new IOException("加载 main.dll 失败（Win32 错误码 = "
                + Marshal.GetLastWin32Error() + "）：" + dll);
        ApplyState(h);
        return h;
    }

    /// <summary>
    /// 把「游戏进程里的密钥状态」搬进当前进程的 main.dll（v0.2 的实验工具）。
    /// 状态文件（XJCodec32.exe 旁的 xj_state.txt，可用环境变量 XJ_STATE 覆盖）
    /// 每行格式： 0x00A1B2C3 &lt;十六进制字节&gt;
    /// </summary>
    private static void ApplyState(IntPtr h)
    {
        string exeDir = Path.GetDirectoryName(
            System.Reflection.Assembly.GetExecutingAssembly().Location);
        string f = Environment.GetEnvironmentVariable("XJ_STATE");
        if (string.IsNullOrEmpty(f)) f = Path.Combine(exeDir, "xj_state.txt");
        if (!File.Exists(f)) return;
        int n = 0, total = 0;
        foreach (string raw in File.ReadAllLines(f))
        {
            string line = raw.Trim();
            if (line.Length == 0 || line[0] == '#' || line[0] == ';') continue;
            string[] tk = line.Split(new[] { ' ', '\t' }, 2,
                                     StringSplitOptions.RemoveEmptyEntries);
            if (tk.Length < 2) continue;
            uint off = ParseU32(tk[0]);
            byte[] data = HexToBytes(tk[1]);
            if (data.Length == 0) continue;
            IntPtr addr = (IntPtr)(h.ToInt64() + off);
            uint old;
            if (!VirtualProtect(addr, (IntPtr)data.Length, PAGE_EXECUTE_READWRITE, out old))
            {
                Console.WriteLine("[WARN] VirtualProtect 失败 @" + tk[0]);
                continue;
            }
            Marshal.Copy(data, 0, addr, data.Length);
            VirtualProtect(addr, (IntPtr)data.Length, old, out old);
            n++;
            total += data.Length;
        }
        Console.WriteLine("[INFO] state=" + f + " 片段=" + n + " 字节=" + total);
    }

    /// <summary>
    /// 批量试密钥：对每一行候选、每一个目标调用 decryption_file(目标, 临时输出, 候选)，
    /// 输出非空即判定该目标命中该候选。
    /// </summary>
    private static int Brute(IntPtr h, string keyFile, string outPrefix, string targetsArg,
                            int startAt, int maxCount)
    {
        IntPtr fn = Export(h, "decryption_file");
        string tmp = outPrefix + ".tmp";                 // 临时输出放在指定目录，避免 %TEMP% 不存在
        string tmpDir = Path.GetDirectoryName(Path.GetFullPath(tmp));
        if (!Directory.Exists(tmpDir)) Directory.CreateDirectory(tmpDir);
        Console.WriteLine("[INFO] tmp=" + tmp);

        List<string> targets = new List<string>();
        foreach (string t in targetsArg.Split(';'))
        {
            string tt = t.Trim();
            if (tt.Length == 0) continue;
            tt = Path.GetFullPath(tt);
            if (!File.Exists(tt)) { Console.WriteLine("[ERR] 找不到目标 " + tt); return 3; }
            targets.Add(tt);
        }
        if (targets.Count == 0) { Console.WriteLine("[ERR] 没有目标"); return 3; }
        foreach (string t in targets) Console.WriteLine("[INFO] target=" + t);

        List<string> keys = new List<string>();
        if (File.Exists(keyFile))
            keys.AddRange(File.ReadAllLines(keyFile, Encoding.UTF8));

        int i = 0, done = 0;
        D3 f = (D3)Marshal.GetDelegateForFunctionPointer(fn, typeof(D3));
        for (int ki = startAt; ki < keys.Count; ki++)
        {
            if (maxCount > 0 && i >= maxCount)
            {
                Console.WriteLine("[INFO] 到达本批上限，续跑到 " + ki);
                return 5;
            }
            i++;
            string k = keys[ki].TrimEnd('\r', '\n');
            if (k.Length == 0 || k[0] == '#') continue;
            IntPtr pk;
            if (k.StartsWith("hex:"))
            {
                byte[] b = HexToBytes(k.Substring(4));
                pk = Marshal.AllocHGlobal(b.Length + 1);
                Marshal.Copy(b, 0, pk, b.Length);
                Marshal.WriteByte(pk, b.Length, 0);
            }
            else
            {
                pk = Utf8(k);
            }
            IntPtr po = Utf8(tmp);
            for (int ti = 0; ti < targets.Count; ti++)
            {
                IntPtr pt = Utf8(targets[ti]);
                if (File.Exists(tmp)) File.Delete(tmp);
                f(pt, po, pk);
                Marshal.FreeHGlobal(pt);
                long n = File.Exists(tmp) ? new FileInfo(tmp).Length : -1;
                if (n > 0)
                {
                    done++;
                    Console.WriteLine("[HIT] 候选#" + (ki + 1) + " 目标[" + ti + "]=" + targets[ti]);
                    Console.WriteLine("[HIT]     key=" + k);
                    string dst = outPrefix + "_" + ti + ".bin";
                    File.Copy(tmp, dst, true);
                    Console.WriteLine("[HIT]     已存 -> " + dst + " (" + n + " 字节)");
                    Console.Out.Flush();
                }
            }
            Marshal.FreeHGlobal(po);
            Marshal.FreeHGlobal(pk);
            if (File.Exists(tmp)) File.Delete(tmp);
            if (i % 100 == 0)
            {
                Console.WriteLine("[..] 本批 " + i + "  绝对位置 " + (ki + 1) + "/" + keys.Count +
                                  "  命中 " + done + "  last=" + k +
                                  " @" + DateTime.Now.ToString("HH:mm:ss"));
                Console.Out.Flush();
            }
        }
        Console.WriteLine("[INFO] 本批结束，命中 " + done);
        return 0;
    }

    private static uint ParseU32(string s)
    {
        s = s.Trim();
        if (s.StartsWith("0x") || s.StartsWith("0X")) return Convert.ToUInt32(s.Substring(2), 16);
        return Convert.ToUInt32(s);
    }

    private static int ParseInt(string s)
    {
        s = s.Trim();
        if (s.StartsWith("0x") || s.StartsWith("0X")) return Convert.ToInt32(s.Substring(2), 16);
        return int.Parse(s);
    }

    private static byte[] HexToBytes(string s)
    {
        StringBuilder sb = new StringBuilder(s.Length);
        foreach (char c in s)
        {
            if (Uri.IsHexDigit(c)) sb.Append(c);
        }
        if (sb.Length % 2 != 0) sb.Length -= 1;
        byte[] b = new byte[sb.Length / 2];
        for (int i = 0; i < b.Length; i++)
            b[i] = Convert.ToByte(sb.ToString(i * 2, 2), 16);
        return b;
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
        if (p == IntPtr.Zero) throw new IOException("main.dll 里没有这个导出函数：" + name);
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

            if (mode == "dump")
            {
                // dump <main.dll> <out.bin> [size]   —— 导出解壳后的内存镜像
                int size = args.Length > 3 ? ParseInt(args[3]) : 0x142000;
                byte[] buf = new byte[size];
                Marshal.Copy(h, buf, 0, size);
                File.WriteAllBytes(Path.GetFullPath(args[2]), buf);
                Console.WriteLine("[INFO] base=0x" + h.ToInt64().ToString("X8"));
                Console.WriteLine("[INFO] size=" + size);
                Console.WriteLine("[OK] dumped");
                return 0;
            }

            if (mode == "brute")
            {
                // brute <main.dll> <密钥候选文件> <输出前缀> <目标1[;目标2;...]> [起点(0基)] [条数]
                // 候选文件每行一个；`hex:` 前缀表示按十六进制原始字节当密钥。
                if (args.Length < 5) { Console.WriteLine("[ERR] 参数不足"); return 2; }
                int st = args.Length > 5 ? ParseInt(args[5]) : 0;
                int cnt = args.Length > 6 ? ParseInt(args[6]) : 0;
                return Brute(h, args[2], args[3], args[4], st, cnt);
            }

            if (mode == "probe")
            {
                // probe <main.dll> <目标密文> <密钥>   —— 单个密钥试一次
                if (args.Length < 4) { Console.WriteLine("[ERR] 参数不足"); return 2; }
                string t = Path.GetFullPath(args[2]);
                string o = t + ".probe_out";
                if (File.Exists(o)) File.Delete(o);
                int r = Call3(Export(h, "decryption_file"), t, o, args[3]);
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

            if (mode == "machine" || mode == "machineid")
            {
                // 取本机机器码：main.dll!get_hard_disk_character()
                // 游戏脚本里就这么取（`GET_HARD_DISK_CHARACTER.call`），
                // 存档里 $game_system.config[:hard_disk_code] 存的就是它。
                IntPtr fn = GetProcAddress(h, "get_hard_disk_character");
                if (fn == IntPtr.Zero)
                {
                    Console.WriteLine("[ERR] main.dll 没有导出 get_hard_disk_character");
                    return 3;
                }
                D0 f = (D0)Marshal.GetDelegateForFunctionPointer(fn, typeof(D0));
                IntPtr sp = f();
                if (sp == IntPtr.Zero)
                {
                    Console.WriteLine("[ERR] get_hard_disk_character 返回空指针");
                    return 4;
                }
                string mid = Marshal.PtrToStringAnsi(sp);
                Console.WriteLine("[INFO] id=" + mid);
                Console.WriteLine("[OK] machine id");
                return 0;
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
