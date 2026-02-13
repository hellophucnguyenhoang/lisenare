import pandas as pd
# Assuming the service is already initialized as per your example
from ai_model_server.services.readmepp_service import readmepp_service

# 1. Load the CSV
file_path = "metadata6.csv"
brick_metadata_df = pd.read_csv(file_path)

# 2. Add the new column by applying the predict function
# return_index=False gives you "A1", "B2", etc.
brick_metadata_df['cefr_level'] = brick_metadata_df['en_source_text'].apply(
    lambda x: readmepp_service.predict(x, return_index=False)
)

# 3. Save the modified dataframe back to CSV if needed
brick_metadata_df.to_csv(file_path, index=False)
