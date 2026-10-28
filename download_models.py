"""
Download official MediaPipe Pose Landmarker models from Google Storage.
Supports Lite and Full models.
"""
import os
import sys
import urllib.request
import ssl

MODELS = {
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "pose_landmarker_full.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
}

def download_file(url: str, dest_path: str):
    print(f"Downloading {os.path.basename(dest_path)}...")
    print(f"  Source: {url}")
    
    # Create unverified SSL context if standard verification fails on some Windows setups
    ctx = ssl.create_default_context()
    
    def reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100.0, downloaded * 100.0 / total_size)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\r  Progress: {percent:5.1f}% ({mb_downloaded:.2f}/{mb_total:.2f} MB)", end="", flush=True)
        else:
            mb_downloaded = downloaded / (1024 * 1024)
            print(f"\r  Downloaded: {mb_downloaded:.2f} MB", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest_path, reporthook=reporthook)
    except Exception as e:
        print(f"\n  Standard download failed: {e}. Retrying without strict SSL check...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx) as response, open(dest_path, 'wb') as out_file:
                total_size = int(response.info().get('Content-Length', -1))
                downloaded = 0
                block_size = 65536
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    if total_size > 0:
                        pct = min(100.0, downloaded * 100.0 / total_size)
                        print(f"\r  Progress: {pct:5.1f}% ({downloaded / (1024*1024):.2f}/{total_size / (1024*1024):.2f} MB)", end="", flush=True)
        except Exception as retry_err:
            print(f"\nError downloading {url}: {retry_err}")
            return False

    print("\n  Download complete!")
    return True

def ensure_models(models_dir: str = None, download_all: bool = False):
    if models_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(base_dir, "models")
    
    os.makedirs(models_dir, exist_ok=True)
    
    # Priority: ensure at least lite model exists, optionally full
    models_to_fetch = MODELS.items() if download_all else [("pose_landmarker_lite.task", MODELS["pose_landmarker_lite.task"])]
    
    for filename, url in models_to_fetch:
        target_path = os.path.join(models_dir, filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            print(f"Model already present: {filename} ({os.path.getsize(target_path)/(1024*1024):.2f} MB)")
        else:
            success = download_file(url, target_path)
            if not success:
                print(f"Failed to download {filename}")
                return False
    return True

if __name__ == "__main__":
    download_both = "--all" in sys.argv
    print("Starting MediaPipe Pose Landmarker model setup...")
    success = ensure_models(download_all=download_both or True) # download both for full options
    if success:
        print("All required models ready!")
    else:
        print("Model setup encountered errors.")
        sys.exit(1)
