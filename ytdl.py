from yt_dlp import YoutubeDL
import os

def get_subtitles(url, lang='en', output_dir="."):
    # Make sure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [lang],
        'skip_download': True,
        'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),

        # Add headers to mimic browser
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/142.0.0.0 Safari/537.36',
        },

        # Retry settings
        'retries': 5,
        'sleep_interval_requests': 1,  # pause 1 second between requests
        'ignoreerrors': True,  # continue if a subtitle fails
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Return the expected file path(s)
    video_id = url.split("v=")[-1]
    vtt_path = os.path.join(output_dir, f"{video_id}.vtt")
    srt_path = os.path.join(output_dir, f"{video_id}.srt")
    return vtt_path, srt_path

url = "https://www.youtube.com/watch?v=zcI9yeI5-6w"
vtt_file, srt_file = get_subtitles(url)
print("Saved subtitles to:", vtt_file, srt_file)
