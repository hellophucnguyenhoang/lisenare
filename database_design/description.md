## 1. Đặc tả bài toán
Người học có thể tham gia bài học cũng như tạo bài học được sắp xếp trong các bộ sưu tập, xem lịch sử học tập của mình cũng như chia sẻ bài học của mình với những người học khác.  

Một **người học** (learner) sẽ có mã người học và tên người học. Một **bài học** (brick) sẽ có một mã bài học, câu ngôn ngữ mẹ đẻ (native language), câu ngôn ngữ mục tiêu (target language), đường dẫn audio của ngôn ngữ mục tiêu, công khai hay không, và thời gian chỉnh sửa cuối cùng. Một **bộ sưu tập** (collection) là một nhóm các brick sẽ có mã collection, tên collection, và ngày được tạo.  

Một learner có thể  **tạo collection**. Một learner có thể  tạo 0 hoặc nhiều collection và một collection phải chỉ có một người tạo ra nó.  

Một learner có thể **tạo brick**, miễn là *không được trùng với bất kỳ brick nào khác đã có trong toàn bộ hệ thống*. Hai brick được gọi là trùng nhau nếu như chúng giống nhau hoàn toàn về ngôn ngữ mẹ đẻ và ngôn ngữ mục tiêu không phân biệt hoa thường và kí tự, ví dụ "I'm Phuc." trùng với "im phuc". Một learner có thể tạo 0 hoặc nhiều brick và một brick phải chỉ được tạo ra bởi một learner.     

Một learner có thể thêm brick bất kỳ vào collection. Một brick cần **thuộc về  ít nhất một hoặc nhiều** collection nhưng một collection có thể có 0 hoặc nhiều brick.  

Một learner sẽ có thể **học** 0 hoặc nhiều brick và ngược lại. Thông tin khi tham gia brick của learner sẽ có các thông tin tùy chọn được cung cấp bởi người dùng là văn bản mục tiêu, audio ghi âm văn bản mục tiêu, điểm thể hiện mức độ tương tự, và còn có thông tin bắt buộc là ngày giờ tham gia.  


Mỗi learner sẽ có một **tài khoản** (account), account sẽ có mã tài khoản, username, mật khẩu, email, thời điểm đăng nhập cuối cùng. Mỗi learner **chỉ có một và chỉ một account**.  
