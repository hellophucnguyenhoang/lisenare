import pandas as pd


def sync_bricks_to_metadata(
    bricks_path: str, metadata_path: str, output_path: str
):
    # 1. Load the CSV files
    bricks = pd.read_csv(bricks_path)
    metadata = pd.read_csv(metadata_path)

    # 2. Create a mapping dictionary from bricks_export.csv
    # Use 'target_text' as the key to find matching rows
    mapping_df = bricks.set_index("target_text")

    # 3. Define which columns to sync
    # Map: {brick_column: metadata_column}
    columns_to_sync = {
        "native_text": "vi_translation",
        "unit_type": "unit_type",
        "structure": "structure",
        "function": "function",
        "grammar_points": "grammar_points",
    }

    # 4. Update the metadata dataframe
    for brick_col, meta_col in columns_to_sync.items():
        # Create a map for the specific column
        mapper = mapping_df[brick_col].to_dict()

        # Apply the map to en_source_text. If no match is found, keep the original value.
        metadata[meta_col] = (
            metadata["en_source_text"].map(mapper).fillna(metadata[meta_col])
        )

    # 5. Save the synced file
    metadata.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Sync complete! Saved to {output_path}")


# Run the sync
sync_bricks_to_metadata(
    bricks_path="bricks_export.csv",
    metadata_path="metadata.csv",
    output_path="metadata_synced.csv",
)
