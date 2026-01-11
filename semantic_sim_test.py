from sentence_transformers import SentenceTransformer, util
sentences = ["What is your age", "How old are you"]

model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
embeddings = model.encode(sentences, convert_to_tensor=True)
cosine_score = util.cos_sim(embeddings[0], embeddings[1])
print(cosine_score.item())

