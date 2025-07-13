import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from pydantic import BaseModel
import dotenv
import os
from strands import Agent, tool
from pydantic import BaseModel
from typing import List
import json
from dataclasses import dataclass
from crawl_web.basic_info import CompanyInfoRetriever
class CompanyInfo(BaseModel):
    ten_cty: str
    ma_ck: str
    dia_chi: str
    so_dt: str
    email: str
    linhvuckinhdoanh: str

@dataclass
class BctcItem:
    quy: str
    tong_tai_san_cuoi_quy: int
    loi_nhuan_sau_thue: int
    loi_nhuan_gop: int
    tong_doanh_thu: int
    tong_tai_san: int
    tong_no: int
    gia_von_hang_ban: int
    loi_nhuan_gop_ve_BH_va_CCDV: int
    loi_nhuan_tai_chinh: int
    loi_nhuan_truoc_thue: int
    tong_tai_san_luu_dong_ngan_han: int
    no_ngan_han: int

class CongTy(BaseModel):
    status: bool
    companyInfo: CompanyInfo
    bctc: List[BctcItem]


output = {'company': {'TenCongTy': 'CÔNG TY CỔ PHẦN VIMC LOGISTICS',
  'MaChungKhoan': 'VLG',
  'DiaChi': 'Phòng 806, tòa nhà Ocean Park, số 1 Đào Duy Anh, phường Phương Mai, quận Đống Đa, TP.Hà Nội, Việt Nam',
  'SoDienThoai': '024-35772047/48',
  'Email': 'info@vimclogistics.vn',
  'LinhVucKinhDoanh': 'Kinh doanh xuất nhập khẩu hàng hóa, môi giới thương mại, đại lý mua bán, ký gửi hàng hóa; Vận tải đa phương thức; vận tải hàng hóa, container, hàng hóa siêu trường, siêu trọng bằng đường bộ, đường sắt, đường biển'},
 'bctc': [{'quy': 'Q1/2025',
   'tong_tai_san_cuoi_quy': 236156479630,
   'loi_nhuan_sau_thue': 1116027647,
   'loi_nhuan_gop': 2304572679,
   'von_chu_so_huu': 178445053214,
   'tong_doanh_thu': 60107916752,
   'tong_tai_san': 236156479630,
   'tong_no': 57711426416,
   'gia_von_hang_ban': 57803344073,
   'loi_nhuan_gop_ve_BH_va_CCDV': 2304572679,
   'loi_nhuan_tai_chinh': 622690374,
   'loi_nhuan_truoc_thue': 1402037633,
   'tong_tai_san_luu_dong_ngan_han': 172374527886,
   'no_ngan_han': 57711426416},
  {'quy': 'Q2/2024',
   'tong_tai_san_cuoi_quy': 212146243168,
   'loi_nhuan_sau_thue': 10588556972,
   'loi_nhuan_gop': 2283265819,
   'von_chu_so_huu': 167262603675,
   'tong_doanh_thu': 42083671325,
   'tong_tai_san': 212146243168,
   'tong_no': 44883639493,
   'gia_von_hang_ban': 39800405506,
   'loi_nhuan_gop_ve_BH_va_CCDV': 2283265819,
   'loi_nhuan_tai_chinh': 189638689,
   'loi_nhuan_truoc_thue': 13259726458,
   'tong_tai_san_luu_dong_ngan_han': 145623535885,
   'no_ngan_han': 44883639493},
  {'quy': 'Q3/2024',
   'tong_tai_san_cuoi_quy': 227375689868,
   'loi_nhuan_sau_thue': 13875548792,
   'loi_nhuan_gop': 1791245409,
   'von_chu_so_huu': 181138152467,
   'tong_doanh_thu': 41977528911,
   'tong_tai_san': 227375689868,
   'tong_no': 46237537401,
   'gia_von_hang_ban': 40186283502,
   'loi_nhuan_gop_ve_BH_va_CCDV': 1791245409,
   'loi_nhuan_tai_chinh': 834803115,
   'loi_nhuan_truoc_thue': 17204922944,
   'tong_tai_san_luu_dong_ngan_han': 162255806260,
   'no_ngan_han': 46237537401},
  {'quy': 'Q4/2024',
   'tong_tai_san_cuoi_quy': 229773312284,
   'loi_nhuan_sau_thue': -3809126900,
   'loi_nhuan_gop': 2114408986,
   'von_chu_so_huu': 177329025567,
   'tong_doanh_thu': 62287700880,
   'tong_tai_san': 229773312284,
   'tong_no': 52444286717,
   'gia_von_hang_ban': 60173291894,
   'loi_nhuan_gop_ve_BH_va_CCDV': 2114408986,
   'loi_nhuan_tai_chinh': 617879595,
   'loi_nhuan_truoc_thue': -513742519,
   'tong_tai_san_luu_dong_ngan_han': 164800586261,
   'no_ngan_han': 52444286717}]}


dotenv.load_dotenv(".env", override=True)
# Create a custom boto3 session
session = boto3.Session(
    aws_access_key_id= os.environ.get('AWS_ACCESS_KEY'),
    aws_secret_access_key= os.environ.get('AWS_SECRET_KEY'),
    # region_name= 'ap-southeast-1'
    
)
boto_config = BotocoreConfig(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=60
)
# Create a Bedrock model with the custom session
bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    boto_session=session,
    temperature=0.3,
    top_p=0.8,
    stop_sequences=["###", "END"],
    # boto_client_config=boto_config,
)


structure_agent = Agent(model =bedrock_model)
output = structure_agent.structured_output(CongTy, f"""
Hãy phân tích và sắp xếp dữ liệu lại đặc biệt về dữ liệu báo cáo tài chính, sắp xếp lại theo list các quý ứng với các biến sắp xếp theo chiều tăng dần về thời gian.
Trả về status: False khi không trích xuất được đủ trường cho 4 quý
{json.dumps(output, ensure_ascii=False)}
""")

company_info_agent = CompanyInfoRetriever()
final = company_info_agent.get_basic_info(f"""
Hãy kiểm tra và cập nhật lại các trường thông tin này giúp tôi. Nếu thông tin không tìm thấy có thể để như cũ. 
Chỉ cần cập nhật lại không cần nói rõ thông tin nào giữ, thông tin nào thay đổi.
{str(output.companyInfo)}
""")

print(final)