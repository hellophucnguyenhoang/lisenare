# Initialize empty list
video_ids = []

# Open the file and read lines
with open("video_ids.txt", "r") as f:
    # Strip newline characters and add to list
    video_ids = [line.strip() for line in f if line.strip()]

print(video_ids)

