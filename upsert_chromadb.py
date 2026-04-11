import os

import chromadb


def migrate_to_single_client(source_folders, target_folder):
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    target_client = chromadb.PersistentClient(path=target_folder)
    MAX_BATCH_SIZE = 5000  # Staying safely under the 5461 limit

    for folder in source_folders:
        if not os.path.exists(folder):
            continue

        print(f"Migrating from: {folder}...")
        source_client = chromadb.PersistentClient(path=folder)
        collection_names = source_client.list_collections()

        for name in collection_names:
            col_name = name if isinstance(name, str) else name.name
            print(f"  -> Collection: {col_name}")

            source_col = source_client.get_collection(name=col_name)
            target_col = target_client.get_or_create_collection(name=col_name)

            # Get data
            data = source_col.get(
                include=["metadatas", "documents", "embeddings"]
            )
            total_items = len(data["ids"])

            if total_items > 0:
                # Process in batches
                for i in range(0, total_items, MAX_BATCH_SIZE):
                    end = i + MAX_BATCH_SIZE
                    print(
                        f"    - Uploading items {i} to {min(end, total_items)}..."
                    )

                    target_col.add(
                        ids=data["ids"][i:end],
                        embeddings=data["embeddings"][i:end],
                        metadatas=data["metadatas"][i:end],
                        documents=data["documents"][i:end],
                    )
                print(f"  Successfully moved {total_items} items.")

    print("\nMigration complete! You can now use './chroma_data'.")


migrate_to_single_client(
    source_folders=["./chroma_ytb_subtitles", "./chroma_bricks"],
    target_folder="./chroma_data",
)
