**BÁO CÁO ĐỊNH NGHĨA**

**VÀ KẾ HOẠCH XÂY DỰNG SẢN PHẨM**

**Thời gian kế hoạch: 30/09/2026 – 18/10/2026**

**1\. Giới thiệu sản phẩm**

Sản phẩm được xây dựng là một **Web Application độc lập** hỗ trợ tự động đề xuất Data Quality Rule cho bảng/cột dữ liệu. Hệ thống nhận thông tin schema, mô tả và đặc trưng profiling của dữ liệu; sau đó sử dụng kết hợp heuristic và LLM để tạo các rule phù hợp, cung cấp bằng chứng và cho phép người dùng review trước khi sử dụng.

**Quyết định phạm vi hiện tại**

Trong 3 tuần này, sản phẩm được phát triển như một hệ thống mới có giao diện Web riêng và backend riêng. Việc tích hợp toàn bộ hệ thống lên UI OpenMetadata được giữ ở hướng phát triển tiếp theo sau khi sản phẩm hoạt động ổn định.

**1.1. Người dùng và mục đích sử dụng**

- Data Engineer chọn một table hoặc cung cấp metadata + profiling của table.
- Hệ thống tự động phân tích và đề xuất các rule có khả năng phù hợp thay vì cấu hình thủ công từng rule.
- Người dùng xem rule, tham số, lý do và evidence; sau đó Accept / Edit / Reject.
- Kết quả recommendation được lưu/đưa ra ở dạng cấu trúc để có thể sử dụng cho bước thực thi DQ hoặc tích hợp hệ thống khác ở giai đoạn sau.

**1.2. Output cuối cùng của sản phẩm**

| **Web UI mới**<br><br>Giao diện chọn dữ liệu, generate rule, xem recommendation và review.      | **Rule Recommendation Engine**<br><br>Sinh Basic rule bằng profiling/heuristic và Advanced rule bằng LLM. |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Validation Layer**<br><br>Kiểm tra column/type, duplicate/conflict và tính hợp lệ của output. | **Recommendation Result**<br><br>Danh sách rule có parameter, reason, evidence và trạng thái review.      |

**2\. Sản phẩm làm được những gì?**

| **Nhóm chức năng**          | **Chức năng**                                                                         | **Output người dùng nhận được**                                              |
| --------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Data Context**            | Đọc/nhận schema, datatype, nullable, description, profiling, existing rule nếu có.    | Context chuẩn cho table/column.                                              |
| **Basic Recommendation**    | Sinh rule từ các pattern có thể suy ra bằng schema + profiling.                       | Not Null, Unique, Between, Length Between, Values In Set, Row Count Between. |
| **Advanced Recommendation** | Dùng LLM theo từng rule type để suy luận semantic và quan hệ nhiều cột.               | Temporal/Cross-column, Conditional Dependency.                               |
| **Validation**              | Kiểm tra column tồn tại, datatype phù hợp, rule trùng/mâu thuẫn và structured output. | Candidate hợp lệ trước khi hiển thị/publish.                                 |
| **Human Review**            | Hiển thị recommendation kèm reason/evidence và cho phép Accept/Edit/Reject.           | Danh sách rule đã được người dùng xác nhận.                                  |

**3\. Phương pháp xây dựng sản phẩm**

Phương án triển khai hiện tại là **xây một sản phẩm Web mới độc lập**, thay vì nhúng chức năng trực tiếp vào giao diện hoặc source code của OpenMetadata. Cách này giúp nhóm tập trung vào giá trị chính của POC: cơ chế recommendation, review và đánh giá chất lượng rule.

**3.1. Thành phần sẽ xây**

| **Thành phần**           | **Vai trò**                                                                                          |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| **Web Frontend**         | Chọn/nhập table context, trigger generate, profiling data, hiển thị rule, reason/evidence và review. |
| **Backend API**          | Điều phối context → recommendation → validation → response cho UI.                                   |
| **Context Builder**      | Chuẩn hóa schema, description và profiling thành input thống nhất.                                   |
| **Basic Rule Engine**    | Heuristic/profile-based generation cho các rule cơ bản.                                              |
| **Advanced Rule Engine** | Rule-type prompt + LLM structured generation cho rule semantic/cross-column.                         |
| **Rule Validator**       | Schema/type/dedup/conflict validation.                                                               |
| **Result/Review Layer**  | Quản lý trạng thái candidate và thao tác Accept/Edit/Reject.                                         |

**4\. Timeline xây dựng trong 3 tuần**

**Mốc chính**

Cuối Tuần 2 phải có sản phẩm chạy end-to-end: Web UI → Generate Basic/Advanced Rule → Validate → Review. Tuần 3 dành cho test, đánh giá, cải thiện chất lượng và hoàn thiện demo/tài liệu.

| **Thời gian**              | **Công việc chính**                                                                                                                | **Output**                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **Tuần 1 - Ngày 30/9**     | Chốt scope sản phẩm, thiết kế UI flow, schema input/output của candidate rule, setup database Postgre, SQL Server và dựng Trino.   | UI flow + Candidate Rule JSON Schema + setup thành công database + Trino |
| **Tuần 1 - Ngày 1-2/10**   | Xây Web UI cơ bản + Backend API; chức năng chọn table/dataset, thống kê và hiển thị metadata/profiling.                            | Web chạy được flow cơ bản.                                               |
| **Tuần 1 - Ngày 3/10**     | Xây Basic Rule Engine từ schema + profiling và nối kết quả lên giao diện.                                                          | Sinh được Basic Rule candidates.                                         |
| **Tuần 2 - Ngày 5-6/10**   | Xây Advanced Rule Engine: prompt/template theo rule type, semantic context và LLM structured output.                               | Sinh được Advanced Rule candidates.                                      |
| **Tuần 2 - Ngày 7/10**     | Xây Rule Validator: kiểm tra column, datatype, duplicate/conflict và output schema.                                                | Candidate được validate trước khi hiển thị.                              |
| **Tuần 2 - Ngày 8/10**     | Hoàn thiện giao diện recommendation: rule, reason/evidence và thao tác Accept / Edit / Reject và đưa kết quả rule lên openmetadata | Human Review hoạt động và tích hợp thành công vào openmetadata           |
| **Tuần 2 - Ngày 9/10**     | Ghép toàn bộ flow Web UI → Backend → Basic/Advanced → Validator → Review; sửa lỗi luồng chính.                                     | Sản phẩm POC hoàn thành end-to-end.                                      |
| **Tuần 3 - Ngày 12-13/10** | Test trên nhiều table/use case; ghi nhận Accept/Edit/Reject và các lỗi recommendation.                                             | Evaluation results.                                                      |
| **Tuần 3 - Ngày 14/10**    | Điều chỉnh heuristic, prompt và validation dựa trên kết quả test.                                                                  | Phiên bản recommendation được cải thiện.                                 |
| **Tuần 3 - Ngày 15/10**    | Hoàn thiện UI, logging/error handling và kịch bản demo.                                                                            | Bản demo ổn định.                                                        |
| **Tuần 3 - Ngày 16/10**    | Tổng hợp kết quả, limitation và hướng phát triển/tích hợp OpenMetadata sau POC.                                                    | Báo cáo cuối + kế hoạch mở rộng.                                         |

**4.1. Mốc kiểm tra tiến độ**

- M1 – cuối Tuần 1: chọn table/context → sinh được Basic Rule trên giao diện.
- M2 – cuối Tuần 2: sản phẩm hoàn chỉnh end-to-end với Basic + Advanced + Validation + Human Review và hiển thị rule lên Openmetadata
- M3 – cuối Tuần 3: có kết quả evaluation, bản demo ổn định và tài liệu bàn giao.

**4.2. Tiêu chí hoàn thành sản phẩm (Definition of Done)**

| **Tiêu chí**                 | **Kết quả mong đợi**                                                                                          |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **Web hoạt động end-to-end** | Chọn/nhập table context → sinh rule → xem recommendation → Accept/Edit/Reject.                                |
| **Basic Rule**               | Sinh được các Basic Rule trong scope POC từ schema/profiling.                                                 |
| **Advanced Rule**            | Sinh được Temporal/Cross-column và Conditional Dependency bằng LLM.                                           |
| **Output chuẩn hóa**         | Mỗi candidate có rule type, target column(s), parameter/expression, reason/evidence và trạng thái validation. |
| **Validation**               | Không hiển thị candidate tham chiếu column không tồn tại hoặc không phù hợp datatype sau validation.          |
| **Human Review**             | Người dùng có thể Accept / Edit / Reject candidate rule trên Web UI.                                          |
| **Tích hợp**                 | Các rule được tạo hiển thị thành công lên Openmetadata                                                        |
| **Stability**                | Demo được luồng chính trên các bảng thử nghiệm mà không lỗi flow end-to-end.                                  |
| **Evaluation**               | Ghi nhận được Accept/Edit/Reject và các lỗi recommendation để phục vụ cải thiện ở Tuần 3.                     |

**5\. Dự kiến phát triển và cải thiện sau POC**

Sau khi sản phẩm standalone ổn định, hướng phát triển không phải xây lại toàn bộ hệ thống mà mở rộng khả năng kết nối, chất lượng recommendation và mức độ tự động hóa.

| **Hướng phát triển**         | **Mục tiêu**                                           | **Dự kiến cải thiện**                                                                                                             |
| ---------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| **Tích hợp OpenMetadata**    | Đưa toàn bộ hệ thống vào workflow metadata/DQ hiện có. | Đọc metadata/profile/existing tests qua API; publish rule đã accept thành Test Case; tận dụng PASS/FAIL/history của OpenMetadata. |
| **Semantic context tốt hơn** | Giúp LLM hiểu đúng ý nghĩa dữ liệu.                    | Khai thác description, glossary, lineage, PK/FK, business policy và domain context.                                               |
| **Advanced rules mở rộng**   | Mở rộng các rule ngoài rule POC.                       | Cross-table rule, Custom SQL phức tạp, timeliness/freshness, relationship/business constraints.                                   |
| **Học từ Human Review**      | Giảm recommendation không phù hợp theo thời gian.      | Lưu Accept/Edit/Reject; dùng lịch sử review để ưu tiên, điều chỉnh threshold/prompt hoặc ranking.                                 |
| **Production hardening**     | Đưa từ POC sang môi trường thực tế.                    | Authentication/authorization, audit log, sensitive-data masking, monitoring, retry/timeout, model/cost control.                   |

**5.1. Sản phẩm kỳ vọng sau 3 tuần**

Một Web Application độc lập có UI riêng, cho phép tạo Data Quality Rule recommendation bằng hai cơ chế Basic (profiling/heuristic) và Advanced (LLM), kiểm tra output bằng Validator, giải thích recommendation, hỗ trợ Human Review và hiển thị rule đề xuất lên Openmetadata