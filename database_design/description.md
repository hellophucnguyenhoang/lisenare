## 1. Đặc tả sơ bài toán
Mô tả này chỉ mô tả những chức năng cốt lõi nhất của ứng dụng.

Người học có thể tham gia bài học cũng như tạo và cấu trúc các bài học trong các bộ sưu tập, xem lịch sử học tập của mình cũng như chia sẻ bài học của mình công khai cho mọi người.  

Một **người học** (learner) sẽ có mã người học và tên người học. Một **bài học** (brick) sẽ có một mã bài học, câu ngôn ngữ mẹ đẻ (native language), câu ngôn ngữ mục tiêu (target language), đường dẫn audio của ngôn ngữ mục tiêu, công khai hay không, và thời gian chỉnh sửa cuối cùng. Một **bộ sưu tập** (collection) là một nhóm các brick sẽ có mã collection, tên collection, và ngày được tạo.  

Một learner có thể **tạo brick**, miễn là *không được trùng với bất kỳ brick nào khác đã có trong toàn bộ hệ thống*. Hai brick được gọi là trùng nhau nếu như chúng giống nhau hoàn toàn về  ngôn ngữ mục tiêu (target_text). Một learner có thể tạo/sở hữu 0 hoặc nhiều brick và một brick phải được tạo ra bởi duy nhất một learner.

Một learner có thể  **tạo collection**. Một learner có thể  tạo 0 hoặc nhiều collection và một collection phải chỉ có một người tạo ra nó.  

Một learner có thể thêm một brick khi họ tự tạo mới hoặc một bản sao của brick gọi là brickoverride khi họ lưu brick của người khác; vào collection của họ để học. Một brick **thuộc về  duy nhất một** collection và một collection phải có ít nhất 1 brick. 

Chủ sở hữu có thể chỉnh sửa brick, nhưng không sửa được target_text, còn người không phải chủ sở hữu chỉ sửa được native_text và audio trên brickoverride. Khi chủ sở hữu muốn xóa một brick, quyền sở hữu sẽ tự chuyển sang người học khác có lượt tương tác trên brick đó cao nhất, nếu không có ai thì sẽ xóa thật.

Mỗi learner sẽ có một **tài khoản** (account), account sẽ có mã tài khoản, username, mật khẩu, email, thời điểm đăng nhập cuối cùng. Mỗi learner **chỉ có một và chỉ một account**.  
