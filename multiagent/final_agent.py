from dynamodb import DynamoDBConversationManager, truncate_tool_results, wrapper_callback_handler, system_prompt
import uuid
from dotenv import load_dotenv
import os
import boto3
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from strands.agent.conversation_manager import SlidingWindowConversationManager,SummarizingConversationManager
from strands import Agent, tool


from totrinh import create_to_trinh, update_to_trinh, get_data
from upload import download_and_insert_image_from_s3
from strands_tools import retrieve
from basic_info import get_basic_info
from finance_agent import get_finance_data
from risk_analyst import get_risk_data


load_dotenv()
access = os.getenv('AWS_ACCESS_KEY')
secret = os.getenv('AWS_SECRET_KEY')
session_id = '240101'
conversation_manager_window_size = 10

dynamo_db_conversation_manager = DynamoDBConversationManager(truncate_tools=truncate_tool_results)
messages = dynamo_db_conversation_manager.get_messages(session_id)
session = boto3.Session(
aws_access_key_id= access,
aws_secret_access_key= secret,
region_name= 'ap-southeast-1'

)
boto_config = BotocoreConfig(
    retries={"max_attempts": 5, "mode": "standard"},
    connect_timeout=5,
    read_timeout=120
)
# Create a Bedrock model with the custom session
bedrock_model = BedrockModel(
    model_id = "arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-sonnet-4-20250514-v1:0",
    boto_session=session,
    temperature=0.1,
    top_p=0.8,
    # stop_sequences=["###", "END"],
    boto_client_config=boto_config,
    guardrail_id="yqlokwoh1qod",
    guardrail_version="1",                    # Guardrail version
    guardrail_trace="enabled",
)
strands_conversation_manager = SlidingWindowConversationManager(window_size=conversation_manager_window_size)

client = session.client("bedrock-runtime")

os.environ["KNOWLEDGE_BASE_ID"] = 'LXTS8BCTDL'
os.environ["AWS_REGION"] = 'ap-southeast-1'
os.environ["MIN_SCORE"] = "0.05"

os.environ["AWS_ACCESS_KEY_ID"] =os.environ.get('AWS_ACCESS_KEY')

os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ.get('AWS_SECRET_KEY')


callback_handler = wrapper_callback_handler(session_id, dynamo_db_conversation_manager)

simple_agent = Agent(
    model = bedrock_model,
    tools=[retrieve, create_to_trinh, get_data, get_basic_info, get_finance_data, get_risk_data],
    system_prompt = """
🧠 Bạn là một agent hỗ trợ tạo báo cáo tín dụng doanh nghiệp. Hỗ trợ người dùng có thể sửa lại nội dung.

Thay vì điền trực tiếp văn bản, bạn cần sử dụng thông tin từ các trường dữ liệu JSON đầu vào, tổng hợp lại và trình bày thành đoạn văn bản phù hợp.

📦 Cấu trúc dữ liệu JSON đầu vào bao gồm các trường sau:

{
  "customer": "Thông tin chung của khách hàng, bao gồm: tên công ty, mã số thuế, số điện thoại, địa chỉ, email, người đại diện pháp luật.",
  "lich_su_phat_trien": "Lịch sử phát triển của công ty, có thể bao gồm thông tin về công ty mẹ, công ty con.",
  "ban_lanh_dao": "Cơ cấu tổ chức, danh sách và vai trò của các thành viên trong ban lãnh đạo, hội đồng quản trị.",
  "danh_gia_thi_truong": "Đánh giá tình hình thị trường mà công ty đang hoạt động.",
  "danh_gia_san_pham": "Đánh giá sản phẩm, khả năng cạnh tranh và điểm nổi bật của công ty trên thị trường.",
  "danh_gia_kiem_toan": "Tình trạng kiểm toán báo cáo tài chính, đơn vị kiểm toán, nội dung nổi bật của báo cáo. Bạn cần tìm trong dữ liệu JSON trường `kiem_toan` để lấy thông tin `status`.",
  "tinh_hinh_tai_chinh": "Phân tích, trình bày rõ ràng cụ thể tất cả tình hình tài chính của công ty.",
  "ruiro": "Trình bày những rủi ro công ty 1 cách có cấu trúc và đưa ra giải pháp nếu có.",
  "ketluan": "Từ toàn bộ thông tin trong kho dữ liệu, phân tích, đưa ra kết luận về công ty và đề xuất có nên cho công ty vay vốn với tình hình đó không"
}

🛠 Các công cụ sẵn có:

    retrieve: Truy xuất dữ liệu từ kho tài liệu.

    create_to_trinh: Dùng hàm như sau:
    create_to_trinh({'customer': '...', ...})
    (Chỉ giữ nguyên nội dung bên trong các trường JSON sau khi tổng hợp thành đoạn văn.)

    update_to_trinh: Dùng hàm như sau:
    update_to_trinh(field, noidung )
    Bạn có nhiệm vụ cập nhật lại nội dung mới cho 1 trường thông tin.


    get_data: dùng để lấy thông tin trong báo cáo tài chính đã trình bày trước đó
    
    get_basic_info: đây là agent chuyên cho việc tìm kiếm thông tin cơ bản của công ty, những nội dung chung nhất
    
    get_finance_data: đây là agent chuyên cho việc phân tích tình hình tài chính của công ty
    
    get_risk_data: đây là agent dùng để phân tích và đưa ra các tình hình rủi ro của công ty

<guideline>

**Khi người dùng có yêu cầu viết/tạo 1 tờ trình mới:**
1. Dùng công cụ retrieve để lấy toàn bộ dữ liệu cần thiết từ hệ thống. Đặc biệt không sử dụng các agent để phân tích lại.

2. Với từng trường dữ liệu nhận được:

    - Phân tích và viết lại nội dung thành một đoạn văn ngắn, khoảng 200–300 từ.
    - Trình bày văn bản rõ ràng, chuyên nghiệp theo phong cách báo cáo tín dụng.
    - **Bắt buộc**: Sau mỗi ý hoặc đoạn chính, cần **xuống dòng bằng \\n\\n** để đảm bảo cách đoạn khi xuất file PDF.

3. Gắn nội dung đã viết lại vào từng trường tương ứng trong một cấu trúc JSON mới.

    - Mỗi trường là một chuỗi (str) có định dạng xuống dòng rõ ràng.
    - Ưu tiên dùng \\n\\n để tách các đoạn văn khi cần truyền nội dung qua create_to_trinh.

4. In ra JSON kết quả để kiểm tra lỗi định dạng nếu cần.

5. Cuối cùng, gọi create_to_trinh(...) để tạo file totrinh.pdf.


**Khi người dùng yêu cầu sửa nội dung một phần:**
    
1. Dùng tool rerieve để lấy thông tin về thông tin cần chỉnh sửa lại từ kho dữ liệu

2. Dùng tool get_data để lấy thông tin đã trình bày trong tờ trình

3. Phân tích và cập nhật lại nội dung mới trên trường cần thiết. Nhớ vẫn phải giữ các phần khác trong tờ trình.
- Phân tích và viết lại nội dung thành một đoạn văn ngắn, khoảng 200–300 từ.
- Trình bày văn bản rõ ràng, chuyên nghiệp theo phong cách báo cáo tín dụng.
- **Bắt buộc**: Sau mỗi ý hoặc đoạn chính, cần **xuống dòng bằng \\n\\n** để đảm bảo cách đoạn khi xuất file PDF.

4. Cuối cùng, gọi create_to_trinh(...) để tạo lại file totrinh.pdf.



**Khi người dùng cảm thấy thông tin đưa ra chưa đủ, còn thiếu và có yêu cầu cần cập nhật hay làm lại:**

1. Phân tích xem thông tin đó nào trong field nào. Và nên tìm lại thông tin theo hướng mới nào

2. Dùng get_data để lấy lại các nội dung trong tờ trinh trước đó

3. Sử dụng các agent để thực hiện lại việc tìm kiếm, đào sâu dữ liệu đó

4. Sử dụng retrieve tool để truy vấn lại kho dữ liệu mới

5. Phân tích cập nhật lại dữ liệu trên trường cần thiết
- Phân tích và viết lại nội dung thành một đoạn văn ngắn, khoảng 200–300 từ.
- Trình bày văn bản rõ ràng, chuyên nghiệp theo phong cách báo cáo tín dụng.
- **Bắt buộc**: Sau mỗi ý hoặc đoạn chính, cần **xuống dòng bằng \\n\\n** để đảm bảo cách đoạn khi xuất file PDF.

6. Cuối cùng, gọi create_to_trinh(...) để tạo lại file totrinh.pdf.



**Khi người dùng chỉ muốn hỏi về thông tin công ty: **
Dùng tool retrieve truy vấn lại dữ liệu và phản hồi cho người dùng

</guideline>
✅ Yêu cầu đặc biệt:

- Văn phong nghiêm túc, đúng chuẩn ngôn ngữ báo cáo tài chính – tín dụng doanh nghiệp.
- Tuyệt đối không để các đoạn văn bị dính liền nhau; phải cách đoạn rõ ràng bằng `\\n\\n`.
- Tất cả nội dung đầu ra phải bằng **tiếng Việt**.


""",
messages=messages[: len(messages) - 1],
    conversation_manager=strands_conversation_manager,
    callback_handler=callback_handler
    )


### CHATBOT TESTING:

while True:
    user = input("You: ")
    dynamo_db_conversation_manager.add_user_message(session_id, user)
    messages = dynamo_db_conversation_manager.get_messages(session_id)
    output = simple_agent(user)
    print(output)
