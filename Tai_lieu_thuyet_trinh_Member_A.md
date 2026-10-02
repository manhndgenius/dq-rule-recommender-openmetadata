## 1. MỞ ĐẦU: BÀI TOÁN & GIẢI PHÁP (Nói trong 1 phút)

> *"Kính thưa thầy/cô (hoặc anh/chị), trong các hệ sinh thái dữ liệu hiện đại như Data Lakehouse hay OpenMetadata, việc đảm bảo chất lượng dữ liệu (Data Quality - DQ) là cực kỳ sống còn.  
> Tuy nhiên, hiện nay Data Engineer phải tự cấu hình thủ công từng rule cho hàng trăm bảng — vừa tốn công sức, vừa dễ bỏ sót lỗi.  
> Nhóm chúng em xây dựng **Data Quality Rule Recommender** — một Web Application độc lập có khả năng tự động đọc siêu dữ liệu (Schema + Profiling) từ OpenMetadata, sau đó dùng thuật toán Heuristic và LLM để tự động gợi ý các luật kiểm tra dữ liệu, minh bạch lý do và hỗ trợ Human-in-the-loop (con người duyệt) trước khi kích hoạt."*

---

## 2. PHÂN CHIA TRÁCH NHIỆM TRONG NHÓM 2 NGƯỜI (Nói trong 30 giây)

> * **Bạn B phụ trách:** Hạ tầng Database, Context Builder, Advanced Engine (LLM suy luận ngữ nghĩa đa cột) và Rule Validator.
> * **Em (Thành viên A) phụ trách 3 nhiệm vụ chính:**
>   1. Xây dựng **Web Application UI** (React SPA) phục vụ việc khám phá dữ liệu và Human Review.
>   2. Xây dựng **Basic Rule Engine** (Hệ thống Heuristic toán học sinh rule dựa trên profiling).
>   3. Tích hợp **REST API OpenMetadata** để kéo Schema và Profiling data về hệ thống."*

---

## 3. CÁC KẾT QUẢ EM ĐÃ HOÀN THÀNH (Nói trong 1.5 phút)

Em đã hoàn thành trọn vẹn 100% các mục tiêu kỹ thuật được giao:

### ① Web UI hiện đại (React 19 + Vite)
* Hỗ trợ cả **Dark Theme và Light Theme** linh hoạt (nút toggle ☀️/🌙 trên thanh Header, lưu trạng thái tự động vào `localStorage`).
* Bố cục 2 phân hệ rõ ràng, responsive:
  * **Cột trái:** Khám phá dữ liệu (Table Context, thẻ KPI số dòng, số cột, bảng phân phối null và distinct).
  * **Cột phải:** Bảng điều khiển sinh rule, bộ lọc thông minh, danh sách thẻ Rule Cards và luồng **Human Review**.
* Hỗ trợ đầy đủ thao tác: **Accept** (duyệt), **Reject** (từ chối), **Edit** (popup chỉnh sửa trực tiếp tham số min/max/SQL) và thanh đo tiến độ review.

### ② Basic Rule Engine (Thuật toán Heuristic chuẩn xác)
Xây dựng trong `backend/engine/basic_engine.py` với **6 luật kiểm tra chất lượng chuẩn OpenMetadata**:
1. **`columnValuesToBeNotNull`**: Tự động phát hiện khi cột có `null_count == 0` (ưu tiên Primary Key).
2. **`columnValuesToBeUnique`**: Nhận diện trường định danh khi `distinct_ratio >= 0.99`.
3. **`columnValuesToBeBetween`**: Tự động chặn khoảng `[min, max]` cho các cột số (Numeric, Integer) và ngày tháng.
4. **`columnValuesToBeInSet`**: Nhận diện cột trạng thái danh mục có độ biến thiên thấp (`cardinality <= 20`).
5. **`columnValuesLengthToBeBetween`**: Đo lường biên độ dài chuỗi ký tự hợp lệ.
6. **`tableRowCountToBeBetween`**: Thiết lập biên độ an toàn cho quy mô tổng số dòng của bảng.

### ③ Kiểm thử chất lượng (Unit Tests)
* Đã viết bộ test tự động tại `tests/test_basic_engine.py`.
* Kết quả chạy `pytest`: **Đạt 100% (7/7 test cases passed)**, bao gồm cả trường hợp bảng rỗng và dữ liệu biên.

### ④ Tích hợp REST API OpenMetadata
* Viết module `openmetadata_client.py` kết nối trực tiếp đến OpenMetadata API để trích xuất `columns`, `tableProfile` và `columnProfile` thay vì chỉ dùng dữ liệu giả lập tĩnh.

---

## 4. KỊCH BẢN THỰC HÀNH DEMO TRỰC TIẾP (LIVE DEMO - 2 ĐẾN 3 PHÚT)

Khi thầy cô hoặc người nghe yêu cầu chiếu sản phẩm, bạn thao tác theo đúng 4 bước sau:

* **Bước 1: Mở trình duyệt vào `http://localhost:5173/`**
  * *Nói:* *"Đây là giao diện Web App của em. Ở thanh trên cùng, hệ thống đang kết nối trực tiếp với Database và OpenMetadata."*
  * *(Tùy chọn bấm nút `☀️ Giao diện Sáng` / `🌙 Giao diện Tối`):* *"Ứng dụng hỗ trợ chuyển đổi linh hoạt giữa giao diện Tối và Sáng, tự động ghi nhớ tùy chọn vào trình duyệt."*
  * *Chỉ vào cột trái:* *"Khi em chọn bảng `orders`, hệ thống lập tức hiển thị Schema và các chỉ số Data Profiling như tổng số 15.420 dòng, tỷ lệ null của từng cột qua các thanh biểu đồ trực quan."*

* **Bước 2: Bấm nút `[ ⚡ Generate Quality Rules ]`**
  * *Nói:* *"Bây giờ em bấm Generate. Hệ thống sẽ kích hoạt Basic Rule Engine do em viết. Thuật toán sẽ phân tích profiling và tự động sinh ra các candidate rules."*
  * *Chỉ vào thẻ rule:* *"Mỗi thẻ rule đều có tên rule chuẩn OpenMetadata, tham số cấu hình, và đặc biệt là có **Lý do (Reason)** kèm **Bằng chứng số liệu (Evidence)** rõ ràng để Data Engineer tin tưởng."*

* **Bước 3: Thực hiện thao tác Human Review**
  * Bấm nút **`Accept`** trên rule Not Null: *"Khi em đồng ý, rule chuyển sang màu xanh và thanh tiến độ Review tăng lên."*
  * Bấm nút **`Edit`** trên rule Between: *"Nếu ngưỡng tối đa 48.500.000 VNĐ quá chặt, em có thể bấm Edit để nâng lên 100.000.000 VNĐ rồi bấm Lưu. Rule sẽ chuyển trạng thái sang EDITED."*
  * Bấm nút **`Reject`** trên 1 rule không cần thiết: *"Rule bị từ chối sẽ mờ đi."*

* **Bước 4: Chạy kiểm thử tự động trên Terminal (Tạo ấn tượng kỹ thuật cao)**
  * Mở terminal gõ: `python -m pytest tests/test_basic_engine.py -v`
  * *Nói:* *"Toàn bộ logic Heuristic của Basic Engine đều có Unit Test kiểm tra chặt chẽ, đạt 7/7 passed chỉ trong 0.1 giây."*

---

## 5. BỘ CÂU HỎI PHẢN BIỆN DỰ KIẾN & CÁCH TRẢ LỜI TỰ TIN (Q&A)

### Câu 1: Tại sao không dùng AI (LLM) để sinh hết tất cả các rule mà phải chia ra Basic Heuristic và Advanced LLM?
👉 **Trả lời:**  
> *"Dạ, các rule cơ bản như Not Null, Unique, Between hay Cardinality thấp hoàn toàn có thể tính toán chính xác 100% bằng toán học và profiling thống kê.  
> Việc dùng Heuristic cho các rule này giúp **tốc độ phản hồi tức thì (<0.1s)**, **chi phí bằng 0** và **không bao giờ bị ảo giác (hallucination)**.  
> Chúng em dành LLM cho phần việc khó hơn của bạn B: phân tích ngữ nghĩa, hiểu mô tả nghiệp vụ và tìm quan hệ chéo nhiều cột (Cross-column)."*

### Câu 2: Lấy khoảng `[min, max]` từ profiling làm rule Between có sợ bị "overfitting" không? (Ví dụ mai có đơn hàng lớn hơn thì sao?)
👉 **Trả lời:**  
> *"Dạ đúng ạ, đây chính là lý do vì sao hệ thống của em **bắt buộc phải có bước Human Review**!  
> Thuật toán chỉ đưa ra con số quan sát được làm 'bằng chứng tham khảo' (Evidence boundary). Data Engineer khi nhìn vào sẽ bấm nút **Edit** để nới lỏng biên an toàn (ví dụ cộng thêm buffer 20% hoặc làm tròn số) trước khi duyệt chính thức."*

### Câu 3: Dữ liệu được lấy từ đâu? Kết nối OpenMetadata như thế nào?
👉 **Trả lời:**  
> *"Dạ, dữ liệu schema và profiling được kéo tự động qua **REST API của OpenMetadata** (`GET /api/v1/tables`).  
> Hệ thống xác thực bằng **JWT Token** (Bearer token). Ngoài ra, trong code em có xây dựng cơ chế Fallback thông minh: nếu môi trường OpenMetadata local chưa bật, ứng dụng vẫn tự động nạp bản schema cache chuẩn để quá trình demo luôn thông suốt."*

### Câu 4: Sau khi duyệt (Accept) xong thì các rule này sẽ đi đâu?
👉 **Trả lời:**  
> *"Dạ, trong phạm vi POC độc lập này, các rule được lưu vào cơ sở dữ liệu ứng dụng kèm lịch sử review (ai duyệt, sửa tham số gì).  
> Ở giai đoạn tiếp theo sau POC, các rule đã duyệt này sẽ được adapter gọi API OpenMetadata để đăng ký trực tiếp thành các **Executable Test Cases** trong Test Suite của OpenMetadata."*

---

💡 **Lời khuyên trước khi thuyết trình:**  
* Mở sẵn 2 cửa sổ: một cửa sổ Web `http://localhost:5173/` và một cửa sổ Terminal mở sẵn lệnh test.
* Giữ bình tĩnh, nói to rõ ràng, bám sát 4 bước kịch bản ở Mục 4 là bạn sẽ đạt điểm tuyệt đối!
