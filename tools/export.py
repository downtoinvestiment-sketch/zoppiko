"""Exports for publishing.

    python3 tools/export.py P01_the_button

- exports/<ep>/<ep>_master.mp4   H.264, high quality, archive and any manual upload
- exports/<ep>/<ep>_upload.mp4   HEVC (hvc1), two-pass, at most 3.7 MB: the browser upload tool accepts up to 3.8 MB per file.
  All four platforms accept HEVC uploads and re-encode them anyway.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dur(path):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                                capture_output=True, text=True).stdout)


def main(ep, limit_mb=3.65):
    src = os.path.join(ROOT, 'renders', ep, '%s_final.mp4' % ep)
    out = os.path.join(ROOT, 'exports', ep); os.makedirs(out, exist_ok=True)
    master = os.path.join(out, '%s_master.mp4' % ep)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src, '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', master], check=True)
    d = dur(src); audio_k = 112
    video_k = int((limit_mb * 8 * 1024 * 1024 / d) / 1000) - audio_k - 40
    up = os.path.join(out, '%s_upload.mp4' % ep)
    log = os.path.join(out, 'x265_2pass')
    common = ['-c:v', 'libx265', '-preset', 'slow', '-b:v', '%dk' % video_k, '-tag:v', 'hvc1', '-pix_fmt', 'yuv420p']
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src] + common +
                   ['-x265-params', 'pass=1:stats=%s.log:log-level=error' % log, '-an', '-f', 'mp4', '/dev/null'], check=True)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', src] + common +
                   ['-x265-params', 'pass=2:stats=%s.log:log-level=error' % log, '-c:a', 'aac', '-b:a', '%dk' % audio_k,
                    '-movflags', '+faststart', up], check=True)
    for f in os.listdir(out):
        if f.startswith('x265_2pass'):
            os.remove(os.path.join(out, f))
    print('master %.1f MB, upload %.2f MB (video %d kb/s)' % (os.path.getsize(master) / 2**20, os.path.getsize(up) / 2**20, video_k))


if __name__ == '__main__':
    main(sys.argv[1])
