import chromadb
import numpy as np

client = chromadb.PersistentClient("chroma_context")
print(f"Available collections: {client.list_collections()}")

snippets_coll = client.get_collection("snippets")

collection_data = snippets_coll.get(include=["embeddings"])
embeddings = collection_data.get("embeddings")  # n x 384 matrix
print(type(embeddings[0]))
print(embeddings.shape)


exit(0)
snippets_mean = np.mean(embeddings, axis=0)
print(np.sum(snippets_mean))
np.save("assets/embeddings/snippets_mean.npy", snippets_mean)
print("Snippets mean embedding updated")
