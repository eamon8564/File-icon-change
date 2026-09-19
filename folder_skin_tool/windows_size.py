"""Read the local Windows stock-folder silhouette, without changing Shell settings."""
import json
import os
from pathlib import Path
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def default_folder_bounds():
    script = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.Drawing;
using System.Runtime.InteropServices;
public class FolderMetric {
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public struct Info {
        public uint size; public IntPtr icon; public int image; public int index;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)] public string path;
    }
    [DllImport("shell32.dll")] static extern int SHGetStockIconInfo(uint id, uint flags, ref Info info);
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr icon);
    public static int[] Bounds() {
        Info info = new Info(); info.size = (uint)Marshal.SizeOf(typeof(Info));
        Marshal.ThrowExceptionForHR(SHGetStockIconInfo(3, 0x100, ref info));
        try {
            using (Icon icon = Icon.FromHandle(info.icon))
            using (Bitmap bitmap = icon.ToBitmap()) {
                int l=bitmap.Width, t=bitmap.Height, r=0, b=0;
                for (int y=0; y<bitmap.Height; y++) for (int x=0; x<bitmap.Width; x++)
                    if (bitmap.GetPixel(x,y).A > 16) {
                        l=Math.Min(l,x); t=Math.Min(t,y); r=Math.Max(r,x+1); b=Math.Max(b,y+1);
                    }
                if (r<=l || b<=t) throw new Exception("Empty stock icon");
                return new int[] { l*512/bitmap.Width, t*512/bitmap.Height,
                                  r*512/bitmap.Width, b*512/bitmap.Height };
            }
        } finally { DestroyIcon(info.icon); }
    }
}
'@
ConvertTo-Json -Compress -InputObject ([FolderMetric]::Bounds())
'''
    executable = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=25,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('无法读取 Windows 默认文件夹大小；当前构图未改变。')
    bounds = tuple(json.loads(result.stdout.strip()))
    if len(bounds) != 4 or not (0 <= bounds[0] < bounds[2] <= 512 and 0 <= bounds[1] < bounds[3] <= 512):
        raise ValueError('系统图标尺寸无效，当前构图未改变。')
    return bounds
