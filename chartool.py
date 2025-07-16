import os
import json
import boto3
# from upload import *
# from upload import *
import io

def generate_quickchart_configs(chart_list):
    chart_output = {}
    color_palette = [
        "rgb(54, 162, 235)",
        "rgb(255, 99, 132)",
        "rgb(255, 206, 86)",
        "rgb(75, 192, 192)",
        "rgb(153, 102, 255)",
        "rgb(201, 203, 207)"
    ]

    for chart_name, chart in chart_list.items():
        chart_type = chart["chart_type"]
        quarters = chart["quarters"]
        metrics = chart["labels"]
        data = chart["data"]

        line_datasets = []
        bar_datasets = []

        for i, metric in enumerate(metrics):
            values = data.get(metric, [])
            color = color_palette[i % len(color_palette)]

            # Heuristic: values under 1000 treated as line data (likely ratio/percentage)
            is_line = all(abs(v) < 1000 for v in values if isinstance(v, (int, float)))

            dataset = {
                "label": metric,
                "data": values,
                "backgroundColor": color,
                "borderColor": color,
                "borderWidth": 2
            }

            if is_line:
                dataset["type"] = "line"
                dataset["fill"] = False
                dataset["yAxisID"] = "y2" if chart_type == "mix" else "y"
                line_datasets.append(dataset)
            else:
                dataset["type"] = "bar"
                dataset["yAxisID"] = "y1" if chart_type == "mix" else "y"
                bar_datasets.append(dataset)

        # Order: line first, then bar
        datasets = line_datasets + bar_datasets

        config = {
            "type": "bar" if chart_type in ["bar", "stacked", "mix"] else "line",
            "data": {
                "labels": quarters,
                "datasets": datasets
            },
            "options": {
                "responsive": True,
                "title": {
                    "display": True,
                    "text": chart_name.replace("_", " ").title(),
                    "fontSize": 18
                },
                "legend": {
                    "display": True,
                    "position": "top"
                },
                "tooltips": {
                    "mode": "index",
                    "intersect": True
                },
                "scales": {
                    "xAxes": [{"stacked": chart_type == "stacked"}],
                    "yAxes": []
                }
            }
        }

        # Y-axes configuration
        if chart_type == "mix":
            config["options"]["scales"]["yAxes"] = [
                {
                    "id": "y1",
                    "position": "left",
                    "stacked": True,
                    "ticks": {"beginAtZero": False}
                },
                {
                    "id": "y2",
                    "position": "right",
                    "gridLines": {"drawOnChartArea": False},
                    "ticks": {"beginAtZero": False}
                }
            ]
        else:
            config["options"]["scales"]["yAxes"] = [
                {
                    "id": "y",
                    "position": "left",
                    "stacked": chart_type == "stacked",
                    "ticks": {"beginAtZero": False}
                }
            ]

        chart_output[chart_name] = config

    return chart_output


@tool
def compute_cal(data):
    def safe_div(x, y):
        try:
            return round(x / y * 100, 2) if y else None
        except Exception:
            return None

    try:
        return {
            "Biên lợi nhuận": safe_div(data.get("loi_nhuan_sau_thue"), data.get("tong_doanh_thu")),
            "ROE - Tỷ suất sinh lời trên vốn chủ": safe_div(data.get("loi_nhuan_sau_thue"), data.get("von_chu_so_huu")),
            "Hiệu suất sử dụng tài sản": safe_div(data.get("tong_doanh_thu"), data.get("tong_tai_san")),
            "Tỷ lệ vốn chủ sở hữu": safe_div(data.get("von_chu_so_huu"), data.get("tong_tai_san")),
            "Tỷ lệ nợ": safe_div(data.get("tong_no"), data.get("tong_tai_san")),
            "Khả năng thanh toán hiện hành": safe_div(data.get("tong_tai_san_luu_dong_ngan_han"), data.get("no_ngan_han")),
            "Biên lợi nhuận gộp": safe_div(data.get("loi_nhuan_gop"), data.get("tong_doanh_thu")),
            "ROA - Tỷ suất sinh lời trên tài sản": safe_div(data.get("loi_nhuan_sau_thue"), data.get("tong_tai_san")),
            "ROCE - Hiệu quả sử dụng vốn": safe_div(data.get("loi_nhuan_truoc_thue"), (data.get("tong_tai_san", 0) - data.get("no_ngan_han", 0))),
            "ROS - Tỷ suất sinh lời trên doanh thu": safe_div(data.get("loi_nhuan_sau_thue"), data.get("tong_doanh_thu")),
        }
    except Exception as e:
        print("⚠️ Lỗi khi tính toán chỉ số:", e)
        print("⚠️ Dữ liệu bị lỗi:", data)
        return {}
        
def transform(datas):
    merged = {
        "data": {
            "stat": {},
            "cal": {}
        }
    }
    chart_list = {
    'Tài sản và hiệu quả sinh lời': {
        'quarters': [],
        'labels': ['tong_tai_san', 'loi_nhuan_sau_thue', 'ROA - Tỷ suất sinh lời trên tài sản'],
        'chart_type': 'mix',
        'data': {}
    },
    'Vốn chủ sở hữu và khả năng sinh lời': {
        'quarters': [],
        'labels': ['von_chu_so_huu', 'loi_nhuan_sau_thue', 'ROE - Tỷ suất sinh lời trên vốn chủ'],
        'chart_type': 'mix',
        'data': {}
    },
    'Doanh thu và hiệu quả': {
        'quarters': [],
        'labels': ['tong_doanh_thu', 'loi_nhuan_sau_thue', 'ROS - Tỷ suất sinh lời trên doanh thu'],
        'chart_type': 'mix',
        'data': {}
    },
    'Biên lợi nhuận và lợi nhuận': {
        'quarters': [],
        'labels': ['Biên lợi nhuận gộp', 'loi_nhuan_sau_thue', 'loi_nhuan_gop'],
        'chart_type': 'mix',
        'data': {}
    },
    'Cơ cấu tài sản nợ': {
        'quarters': [],
        'labels': ['tong_tai_san', 'tong_no', 'Tỷ lệ nợ'],
        'chart_type': 'stacked',
        'data': {}
    },
    'Phân tích lợi nhuận': {
        'quarters': [],
        'labels': ['loi_nhuan_sau_thue', 'loi_nhuan_truoc_thue', 'loi_nhuan_gop'],
        'chart_type': 'bar',
        'data': {}
    },
    'Cơ cấu vốn': {
        'quarters': [],
        'labels': ['von_chu_so_huu', 'tong_no', 'tong_tai_san'],
        'chart_type': 'stacked',
        'data': {}
    },
    'Hiệu suất và khả năng thanh toán': {
        'quarters': [],
        'labels': ['Hiệu suất sử dụng tài sản', 'ROA - Tỷ suất sinh lời trên tài sản', 'Khả năng thanh toán hiện hành'],
        'chart_type': 'line',
        'data': {}
    }
}
    # Financial metric calculator
    

    for d in datas:
        quarter = d["quy"]
        stat = {k: v for k, v in d.items() if k != "quy"}
        cal = compute_cal(stat)

        # Save to merged dictionary
        merged["data"]["stat"][quarter] = stat
        merged["data"]["cal"][quarter] = cal

        # Fill each chart's data
        for chart in chart_list.values():
            chart["quarters"].append(quarter)
            for label in chart["labels"]:
                # Initialize list if not already
                if label not in chart["data"]:
                    chart["data"][label] = []
                # Get value from stat or cal
                value = stat.get(label) if label in stat else cal.get(label)
                chart["data"][label].append(value)
    return merged, chart_list

from quickchart import QuickChart
import os
from upload import *
from dotenv import load_dotenv
load_dotenv()
access = os.getenv('accesskey')
secret = os.getenv('serectkey')

def save_charts_with_quickchart(chart_configs, output_dir):
    """
    Given chart configs in QuickChart format, render and save them as PNG images to a local folder.
    
    :param chart_configs: dict of {chart_name: quickchart_config}
    :param output_dir: folder to save PNG files
    """
    os.makedirs(output_dir, exist_ok=True)
    

    for name, config in chart_configs.items():
        qc = QuickChart()
        qc.width = 800
        qc.height = 500
        qc.device_pixel_ratio = 2.0
        qc.config = config

        output_path = os.path.join(output_dir, f"{name}.png")

        try:
            # Get image bytes
            img_bytes = qc.get_bytes()

            # Save directly to file
            with open(output_path, "wb") as f:
                f.write(img_bytes)

            print(f"Saved chart: {output_path}")

        except Exception as e:
            print(f"ERROR saving chart '{name}':", e)



def get_chart_context(images):
    # Add instruction to describe each chart and return structured JSON
    images.append({
        "type": "text",
        "text": (
            "Hãy mô tả nội dung của từng ảnh một cách chi tiết dưới dạng JSON, "
            "với cấu trúc: { \"chart_name\": \"phân tích\" }. "
            "Sau đó, đưa ra một kết luận tổng thể dựa trên tất cả các ảnh dưới key `tong_quan`."
        )
    })

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0,
        "system": (
            "Bạn là một chuyên gia phân tích tài chính. Với mỗi biểu đồ tài chính "
            "được cung cấp (ảnh), hãy đánh giá tình hình tài chính của công ty và "
            "xuất kết quả phân tích theo dạng JSON. Mỗi ảnh có key tên biểu đồ. "
            "Thêm phần `tong_quan` cuối cùng để tổng kết toàn bộ ảnh."
        ),
        "messages": [
            {
                "role": "user",
                "content": images
            }
        ]
    }

    session = boto3.Session(
        aws_access_key_id= access,
        aws_secret_access_key=secret,
        region_name="ap-southeast-1"
    )
    client = session.client("bedrock-runtime")

    response = client.invoke_model(
        modelId='arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0',
        contentType='application/json',
        accept='application/json',
        body=json.dumps(payload)
    )
    print(response)
    response_body = json.loads(response['body'].read())
    # print("\nClaude Response:\n")
    raw_text = response_body["content"][0]["text"]

    try:
        structured_output = json.loads(raw_text)
    except json.JSONDecodeError:
        print("⚠️ Output is not valid JSON. Raw output:")
        print(raw_text)
        return None

    return structured_output

def images_as_base64_blocks_from_local(folder_path):
    images = []
    for fname in os.listdir(folder_path):
        if fname.endswith(".png"):
            with open(os.path.join(folder_path, fname), "rb") as f:
                img_bytes = f.read()
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                images.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64
                    }
                })
    return images


def table_for_report(data:dict, output_dir:str):
        # Convert to DataFrames and transpose
        stat_df = pd.DataFrame(data['data']['stat']).T
        cal_df = pd.DataFrame(data['data']['cal']).T
        
# Drop column if it exists (some quarters use a different key spelling)
        stat_df.drop(columns=[col for col in ['loi_nhuan_gop_ve_bh_va_ccdv', 'loi_nhuan_gop_ve_BH_va_CCDV'] if col in stat_df.columns], inplace=True)

        # Rename columns for 'stat'
        stat_df.rename(columns={
            'tong_tai_san': 'Tổng tài sản',
            'tong_no': 'Tổng nợ',
            'von_chu_so_huu': 'Vốn chủ sở hữu',
            'tong_doanh_thu': 'Tổng doanh thu',
            'gia_von_hang_ban': 'Giá vốn hàng bán',
            'loi_nhuan_gop': 'Lợi nhuận gộp',
            'loi_nhuan_sau_thue': 'Lợi nhuận sau thuế',
            'loi_nhuan_truoc_thue': 'Lợi nhuận trước thuế',
            'no_ngan_han': 'Nợ ngắn hạn',
            'tong_tai_san_luu_dong_ngan_han': 'Tổng tài sản lưu động ngắn hạn',
            'tong_tai_san_cuoi_quy': 'Tổng tài sản cuối quý',
            'loi_nhuan_tai_chinh': 'Lợi nhuận tài chính',
        }, inplace=True)

        # Rename columns for 'cal'
        cal_df.rename(columns={
            'ROA - Tỷ suất sinh lời trên tài sản': 'Tỷ suất sinh lời tài sản (ROA)',
            'ROE - Tỷ suất sinh lời trên vốn chủ': 'Tỷ suất sinh lời vốn chủ (ROE)',
            'Tỷ lệ nợ': 'Tỷ lệ nợ',
            'Tỷ lệ vốn chủ sở hữu': 'Tỷ lệ vốn chủ',
            'Khả năng thanh toán hiện hành': 'Hệ số thanh toán hiện hành',
            'Biên lợi nhuận gộp': 'Biên LN gộp',
            'Hiệu suất sử dụng tài sản': 'Hiệu suất sử dụng tài sản',
            'Biên lợi nhuận': 'Biên lợi nhuận',
        }, inplace=True)

        # Plot as tables using matplotlib
        def plot_table(df, title):
            fig, ax = plt.subplots(figsize=(12, len(df.columns)*0.5 + 2))
            ax.axis('off')
            table = ax.table(cellText=df.round(2).values, colLabels=df.columns, rowLabels=df.index, loc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1.2, 1.2)
            # ax.set_title(title, fontweight='bold')
            fig.suptitle(title, fontsize=14, fontweight='bold', y=1.02)  # y>1 pushes above
            fig.tight_layout()
            fig.subplots_adjust(top=0.85) 
            return fig
        stat_df=stat_df.T
        cal_df=cal_df.T
        stat_fig = plot_table(stat_df[['Q2/2024','Q3/2024','Q4/2024','Q1/2025']], "Bảng Chỉ số Tài chính (Tổng hợp)")
        cal_fig = plot_table(cal_df[['Q2/2024','Q3/2024','Q4/2024','Q1/2025']], "Bảng Tỷ số Tài chính Hiệu quả")

        stat_fig.tight_layout()
        cal_fig.tight_layout()
        try:
            stat_fig.savefig(f"{output_dir}/Báo cáo tài chính tổng hợp.png", dpi=300, bbox_inches='tight')
            cal_fig.savefig(f"{output_dir}/Chỉ số hiệu quả tài chính.png", dpi=300, bbox_inches='tight')
            print('Saved image tables')
        except Exception as e:
            print(f'Error: {e}')
def snake_to_pascal(s):
    return '_'.join([word.capitalize() for word in s.split('_')])


@tool
def analyze_financial_data(quarterly_data: list):


    # Step 1: Compute metrics per quarter
    enriched_data = []
    for entry in quarterly_data:
        try:
            cal = compute_cal(entry)
            enriched = entry.copy()
            enriched.update(cal)
            enriched_data.append(enriched)
        except Exception as e:
            entry["error"] = f"Error: {e}"
            enriched_data.append(entry)

    # Step 2: Transform to chart data
    transformed, chart_list = transform(enriched_data)
    print(transformed)
    # Step 3: Generate chart configs and images
    chart_configs = generate_quickchart_configs(chart_list)
    output_dir = "charts"
    save_charts_with_quickchart(chart_configs, output_dir)
    table_for_report(transformed,output_dir)
    # Step 4: Get base64 images & captions
    images = images_as_base64_blocks_from_local(output_dir)
    captions = get_chart_context(images)

    # Step 5: Format final result
    def snake_to_pascal(s): return '_'.join(w.capitalize() for w in s.split('_'))

    result = []
    for chartname in chart_list:
        path = f"{output_dir}/{chartname}.png"
        caption = captions.get(snake_to_pascal(chartname), "Không có mô tả.")
        result.append({
            "chartname": chartname,
            "chartpath": path,
            "chartcaption": caption
        })

    return result

if __name__=="__main__":
    data = [
    {
    "quy": "Q1/2025",
    "tong_tai_san_cuoi_quy": 3242801930898, 
    "loi_nhuan_sau_thue": -116915411380,
    "loi_nhuan_gop": -61372849620,
    "von_chu_so_huu": 119953583407,
    "tong_doanh_thu": 74478217583,
    "tong_tai_san": 3242801930898,
    "tong_no": 3122848347491,
    "gia_von_hang_ban": 135851067203,
    "loi_nhuan_gop_ve_BH_va_CCDV": -61372849620,
    "loi_nhuan_tai_chinh": -53217597991,
    "loi_nhuan_truoc_thue": -116888181727,
    "tong_tai_san_luu_dong_ngan_han": 2285669507340,
    "no_ngan_han": 2524167001622
    },
    {
    "quy": "Q2/2024",
    "tong_tai_san_cuoi_quy": 3888127929013,
    "loi_nhuan_sau_thue": -39411140488,
    "loi_nhuan_gop": -14535635495,
    "von_chu_so_huu": 639804256084,
    "tong_doanh_thu": 25303024143,
    "tong_tai_san": 3888127929013,
    "tong_no": 3248323672929,
    "gia_von_hang_ban": 39838659638,
    "loi_nhuan_gop_ve_BH_va_CCDV": -14535635495,
    "loi_nhuan_tai_chinh": -21624894106,
    "loi_nhuan_truoc_thue": -39411140488,
    "tong_tai_san_luu_dong_ngan_han": 2645837926158,
    "no_ngan_han": 1794456519079
    },
    {
    "quy": "Q3/2024",
    "tong_tai_san_cuoi_quy": 3813551935399,
    "loi_nhuan_sau_thue": -52971181445,
    "loi_nhuan_gop": 2077811611,
    "von_chu_so_huu": 512359235517,
    "tong_doanh_thu": 25826311936,
    "tong_tai_san": 3813551935399,
    "tong_no": 3301192699882,
    "gia_von_hang_ban": 23748500325,
    "loi_nhuan_gop_ve_bh_va_ccdv": 2077811611,
    "loi_nhuan_tai_chinh": -51327780954,
    "loi_nhuan_truoc_thue": -52971181392,
    "tong_tai_san_luu_dong_ngan_han": 2607354571405,
    "no_ngan_han": 2453654772417
    },
    {
    "quy": "Q4/2024",
    "tong_tai_san_cuoi_quy": 3337972266791,
    "loi_nhuan_sau_thue": -214198247455,
    "loi_nhuan_gop": 123088516,
    "von_chu_so_huu": 298160982194,
    "tong_doanh_thu": 184348685030,
    "tong_tai_san": 3337972266791,
    "tong_no": 3039811284597,
    "gia_von_hang_ban": 184225596514,
    "loi_nhuan_gop_ve_BH_va_CCDV": 123088516,
    "loi_nhuan_tai_chinh": -52153621130,
    "loi_nhuan_truoc_thue": -214198247455,
    "tong_tai_san_luu_dong_ngan_han": 2357624604751,
    "no_ngan_han": 2441157168380
    }
]
    print(analyze_financial_data(data))


