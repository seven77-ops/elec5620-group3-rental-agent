"""Read-only product explanations have a distinct evidence scope from rental rules."""
import re

REFERENCE_TYPES=('official_guidance','official_template','student_guidance')
PRODUCT_TYPES=('product_guide',)
_EXPLANATION=re.compile(r'^\s*(?:(?:how|where|why|what|when)\b|(?:do i|does|is|are|can i|should i|will i)\b|(?:please\s+)?(?:explain|tell me|show me)\b|(?:can|could) you (?:explain|tell me|show me)\b)|怎么|如何|怎样|在哪|哪里|是什么|什么是|区别|有什么用|会不会|是否|能否|需要.*吗',re.I)
_PRODUCT=re.compile(
    r'\b(?:this (?:app|website)|rental assistant|user guide|product guide|new case|new conversation|rental requirements|cloud consent|contract search|local indexing)\b|'
    r'\bupload\b.{0,25}\bcontract\b|'
    r'\b(?:electricity providers?|utility providers?|provider cards?|moving booking|cleaning booking|inspection (?:questions|checklist)|bond follow[ -]?up|move[ -]?out plan|repair follow[ -]?up|lifestyle preferences)\b|'
    r'\b(?:favou?rit(?:es?|ing)|shortlist|saved (?:homes?|properties|listings?)|commute filter|filter chips?)\b|'
    r'\b(?:select\w*|compar\w*)\b.{0,35}\b(?:homes?|houses?|properties|listings?)\b|'
    r'\b(?:generate|preview|download|fill\w*)\b.{0,35}\b(?:lease draft|contract draft)\b|'
    r'\b(?:polish|rewrite|draft)\b.{0,30}\b(?:repair email|maintenance email)\b|'
    r'收藏|选定并跟进|我的租房需求|租房需求|筛选条件|这个网站|这个系统|租房助手|使用指南|润色报修邮件|新建案例|上传合同|撤销授权',re.I)
_ACTION=re.compile(r'(?:^|[.!?;]\s*|\b(?:and then|then)\s+)(?:please\s+)?(?:select|save|compare|generate|upload|delete|revoke|start|update|edit|polish|rewrite|open|favorite|favourite)\b|(?:^|[，,。；;]\s*)(?:请|帮我|然后)(?:直接)?(?:收藏|选定|保存|比较|生成|上传|撤销)|(?:^|[，,。；;]\s*)(?:收藏|选定|保存|比较|生成|上传|撤销)(?:这|那|第|一份|一个|我的)',re.I)


def is_product_question(question):
    if not isinstance(question,str) or _ACTION.search(question):return False
    if re.search(r'\b(?:NCAT|Tribunal|court)\b',question,re.I) and not re.search(r'\b(?:this app|this website|rental assistant)\b',question,re.I):return False
    return bool(_EXPLANATION.search(question) and _PRODUCT.search(question))


def retrieval_source_types(question):
    return PRODUCT_TYPES if is_product_question(question) else REFERENCE_TYPES


def retrieval_query(question):
    if not is_product_question(question):return question
    bridges={'收藏':'favorites comparison','选定':'select follow up','租房需求':'rental requirements filters',
             '筛选':'filters requirements','新建案例':'new case','上传合同':'upload contract',
             '撤销授权':'revoke consent','报修邮件':'repair email polish','指南':'user guide'}
    return question+' '+' '.join(value for key,value in bridges.items() if key in question)
