## 1. Đặc tả sơ bài toán

Người học có thể tạo, học, và quản lý các bài học trong các bộ sưu tập, xem thống kê học tập.
Cân nhắc xây dựng chức năng sao cho thuận tiện cho việc xây dựng chức năng chia sẻ bài học của trong cộng đồng sau này.

Mỗi người học (**Learner**) được định danh bởi mã người học và tên.

Mỗi bài học (**Brick**) bao gồm mã bài học, câu ngôn ngữ mẹ đẻ (native text), câu ngôn ngữ mục tiêu (target text), đường dẫn tệp âm thanh của target text, tùy chọn cách phát âm của target_text, riêng tư hay không, và thời điểm chỉnh sửa gần nhất.
Độ dài của target text không quá 25 từ.

Một bộ sưu tập (**Collection**) là tập hợp các brick, gồm mã bộ sưu tập, tên bộ sưu tập, và ngày tạo.

Một learner có thể tạo một hoặc nhiều brick, đồng thời sở hữu brick họ tạo.
*Learner chỉ có thể chỉnh sửa brick họ sở hữu.*

Learner có thể luyện tập (nói) một brick họ sở hữu, kết quả sẽ được dùng cho việc lập lịch ôn tập tiếp theo.
Learner cần biết thời gian và số lần ôn tập và các thống kê hữu ích khác có liên quan đến việc theo dõi trình độ học.

Một learner có thể tạo một collection, collection này có thể rỗng.
Mỗi brick chỉ thuộc về một collection duy nhất, và mỗi collection phải chứa ít nhất một brick.

Một tài khoản (**Account**) gồm mã tài khoản, username, password, tùy chọn email address để đổi password, và thời điểm đăng nhập gần nhất.
Mỗi learner sở hữu đúng một và không dùng chung account.

Một bài viết (**Snippet**) bao gồm mã snippet, nội dung, ngôn ngữ, tùy chọn âm thanh, và thời điểm chỉnh sửa gần nhất.

Snippet là công khai (hoặc giữa những learner bạn bè với nhau sau này).
Những learner khác có thể đóng góp âm thanh cho snippet đó.
Những learner khác có thể vote chất lượng âm thanh, hoặc báo cáo snippet về bản quyền, nội dung nhạy cảm,...

Một thẻ (**Tag**) sẽ bao gồm mã tag, và tên.

Người học có thể thêm các thẻ (Tags) cho Brick, Collection,... để phục vụ mục đích cá nhân như gom nhóm và phân loại một cách linh hoạt.
