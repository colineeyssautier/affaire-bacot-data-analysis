import pandas as pd

df = pd.read_json("videos_youtube.json")  # ou le nom réel du fichier
videos_deja_scrapees = df["video_id"].unique()
print(f"{len(videos_deja_scrapees)} vidéos trouvées")
print(videos_deja_scrapees)