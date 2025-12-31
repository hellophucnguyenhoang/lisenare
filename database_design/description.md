## 1. Đặc tả bài toán
Người học có thể tham gia bài học cũng như tạo bài học, xem lịch sử học tập của mình cũng như chia sẻ bài học của mình với những người học khác.  

Một **người học** (learner) sẽ có mã người học, tên người học và trình độ hiện tại(1). Một **bài học** (được gọi là một brick) sẽ có một mã bài học, câu ngôn ngữ mẹ đẻ (native language), câu ngôn ngữ mục tiêu (target language), đường dẫn audio của ngôn ngữ mục tiêu, và public hay không. Một **collection** là một nhóm các brick sẽ có mã collection, tên collection, và ngày được tạo.  

Một người học sẽ có thể **tham gia** vào từ 0, một hoặc nhiều bài học và ngược lại. Thông tin khi tham gia bài học của người dùng sẽ có các thông tin tùy chọn được cung cấp bởi người dùng là văn bản mục tiêu, audio ghi âm văn bản mục tiêu; ngoài ra còn có các thông tin bắt buộc khác như ngày giờ tham gia.  

Một người học cũng có thể **tạo bài học**, miễn là bài học đó không trùng với một bài học khác. Một bài học được gọi là trùng nếu như giống nhau hoàn toàn về ngôn ngữ mẹ đẻ và ngôn ngữ mục tiêu. Một người dùng có thể tạo nhiều bài học và một bài học chỉ được tạo ra bởi một người dùng. Một bài học cần **thuộc về ít nhất  một** collection, và một collection không cần phải có bài học.  

Mỗi người dùng sẽ có một **tài khoản** người học, tài khoản người học sẽ có mã tài khoản, username, mật khẩu, email, lần đăng nhập cuối. Mỗi người học **chỉ có một và chỉ một tài khoản** học tập.  

Note:  
(1): Trình độ hiện tại này hơi khó xác định nếu như không có một chuẩn chung. Cân nhắc xác định thông qua một bài test nhỏ. Chắc sẽ lấy chuẩn 6 mức CEFR (A1 - C2). Hoặc là không cần xác định luôn.

