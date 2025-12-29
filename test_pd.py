import pandas as pd
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

df = pd.read_csv("bricks/metadata.csv")
model_name = "VietAI/envit5-translation"
tokenizer = AutoTokenizer.from_pretrained(model_name)  
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

def translate_batch(input_sentences):
    """
    inputs = [
        "vi: VietAI là tổ chức phi lợi nhuận với sứ mệnh ươm mầm tài năng về trí tuệ nhân tạo và xây dựng một cộng đồng các chuyên gia trong lĩnh vực trí tuệ nhân tạo đẳng cấp quốc tế tại Việt Nam.",
        "vi: Theo báo cáo mới nhất của Linkedin về danh sách việc làm triển vọng với mức lương hấp dẫn năm 2020, các chức danh công việc liên quan đến AI như Chuyên gia AI (Artificial Intelligence Specialist), Kỹ sư ML (Machine Learning Engineer) đều xếp thứ hạng cao.",
        "en: Our teams aspire to make discoveries that impact everyone, and core to our approach is sharing our research and tools to fuel progress in the field.",
        "en: We're on a journey to advance and democratize artificial intelligence through open source and open science."
    ]
    outputs = [
        'en: VietAI is a non-profit organization with the mission of nurturing artificial intelligence talents and building an international - class community of artificial intelligence experts in Vietnam.',
        'en: According to the latest LinkedIn report on the 2020 list of attractive and promising jobs, AI - related job titles such as AI Specialist, ML Engineer and ML Engineer all rank high.',
        'vi: Nhóm chúng tôi khao khát tạo ra những khám phá có ảnh hưởng đến mọi người, và cốt lõi trong cách tiếp cận của chúng tôi là chia sẻ nghiên cứu và công cụ để thúc đẩy sự tiến bộ trong lĩnh vực này.',
        'vi: Chúng ta đang trên hành trình tiến bộ và dân chủ hoá trí tuệ nhân tạo thông qua mã nguồn mở và khoa học mở.'
    ]
    """
    outputs = model.generate(tokenizer(input_sentences, return_tensors="pt", padding=True).input_ids.to('cpu'), max_length=512)
    return tokenizer.batch_decode(outputs, skip_special_tokens=True)

source_sentences = ["en: " + s for s in df['source_text'].tolist()]
target_sentences = []
batch_size = 16
for i in range(0, len(source_sentences), batch_size):
    source_sentence_batch = source_sentences[i:i+batch_size]
    target_sentence_batch = translate_batch(source_sentence_batch)
    target_sentence_batch = [target_sentence[4:] for target_sentence in target_sentence_batch]
    target_sentences.extend(target_sentence_batch)
    print(f"{i}/{len(source_sentences)}")

df['target_text'] = target_sentences
df.to_csv("bricks/metadata.csv", index=False)
