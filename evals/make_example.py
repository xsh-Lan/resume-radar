"""Hand-authored fictional ledger examples, not model-generated quality measurements."""
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from workflow import initialize,read_json,write_json

RESUME='# 示例候选人\n- 访谈8名商家，识别优惠配置入口难找的问题。\n- 整理问题清单并绘制调整原型，提交负责人评审，尚未上线。\n- 计划上线后跟踪咨询量变化。\n- 使用表格核对活动报名记录中的重复项。\n'
JD='产品实习：参与需求调研与原型设计。\n协助制定验证方法并根据实际使用反馈迭代。\n'

def build_example(parent,mode):
    parent=Path(parent); parent.mkdir(parents=True,exist_ok=True)
    resume=parent/'resume.txt'; jd=parent/'jd.txt'
    resume.write_text(RESUME,encoding='utf-8'); jd.write_text(JD,encoding='utf-8')
    root=parent/'run'
    initialize(SimpleNamespace(resume=str(resume),jd=str(jd) if mode=='jd' else None,
               target='产品实习' if mode!='explore' else None,stage='实习',candidate_key='fictional-example',run_dir=str(root),redact_name=[]))
    sources=read_json(root/'sources.json')['sources']; units=sources[0]['units']
    evidence=[]
    for i,u in enumerate(units,1):
        evidence.append({'id':f'E{i}','source_id':'RESUME','unit_id':u['id'],'quote':u['text'],
                         'status':'self_reported','actor':'individual' if i!=1 else 'unknown',
                         'action':'身份信息' if i==1 else u['text'],
                         'completion':'expected' if i==4 else 'actual','deliverable':'按所引原文','metrics':[]})
    write_json(root/'evidence.json',evidence)
    reqs=[]
    for i,(description,task,responsibility,depth,support,eids) in enumerate([
        ('需求调研与原型交付','理解商家操作问题并表达调整方案','协助调研与原型设计','说明如何从访谈发现形成方案','direct',['E2','E3']),
        ('验证方法与反馈迭代','判断方案是否解决原问题','协助建立可执行的验证方式','说明准备观察什么及为何能验证方案','partial',['E3','E4'])],1):
        reqs.append({'id':f'R{i}','role':'产品实习','basis':'jd' if mode=='jd' else 'role_standard',
                     'source_unit_ids':[sources[1]['units'][i-1]['id']] if mode=='jd' else [],
                     'basis_note':'' if mode=='jd' else '基于产品实习的方向级任务分析；未据此推断任何公司的硬门槛。',
                     'description':description,'task':task,'responsibility':responsibility,'decision_depth':depth,
                     'importance':'core','support':support,'evidence_ids':eids})
    write_json(root/'requirements.json',reqs)
    diagnosis={'id':'D1','issue_key':'prototype-validation-method','priority':'high','scope':'role','gap_type':'evidence_missing','requirement_ids':['R2'],'evidence_ids':['E3','E4'],
               'demonstrates':'已有原型交付，并提出上线后观察咨询量的计划。',
               'does_not_demonstrate':'材料尚未说明咨询量如何对应入口问题，或是否另有任务完成率等验证方法。',
               'impact':'能支持设计与交付经历；对于要求验证和迭代的任务，招聘者仍难判断候选人的效果判断方法。',
               'question':'除咨询量外，你是否设计过与入口问题直接对应的验证任务或反馈方式？具体是什么？',
               'next_action':'先补充已有验证方法及选择依据；尚未做过时再制定真实的小规模验证，不把计划写成结果。'}
    write_json(root/'diagnosis.json',[diagnosis])
    reviews=[]
    reasons=['客观标识，简短检查；不据此推断能力。','对象、个人动作和发现明确，保留好句。',
             '交付与当前阶段明确，保留未上线边界。','观察计划已说明，但与问题之间的验证逻辑仍需确认。',
             '能支持记录核对与基础数据处理；对当前产品方向是辅助证据，可视版面压缩。']
    capabilities=['客观信息，不单独推断能力','访谈与问题归纳','原型交付与贡献边界','效果观察意图，方法尚未明确','记录整理与基础核对']
    for i,u in enumerate(units,1):
        reviews.append({'id':f'S{i}','unit_ids':[u['id']],'decision':'needs_input' if i==4 else 'keep',
                        'reason':reasons[i-1],'capability':capabilities[i-1],
                        'role_relevance':'对应R2的效果判断' if i==4 else '对应目标方向的证据或简短信息检查',
                        'diagnosis_ids':['D1'] if i==4 else [],'evidence_ids':[f'E{i}'],'text':'',
                        'question':diagnosis['question'] if i==4 else ''})
    write_json(root/'sentence_review.json',reviews)
    run=read_json(root/'run.json'); run.update(status='reviewed',summary='虚构教学案例：访谈、问题归纳与原型交付的证据清楚；最重要的未知是验证方式与用户问题是否对应，先澄清方法，不把尚未上线误判为没有产品能力。',
        actions=[{'type':'evidence','text':diagnosis['next_action'],'diagnosis_ids':['D1']}],
        review={'status':'completed','findings':['D1区分计划与实际结果；E3明确未上线；S2与S3保留好句；尚未证明的验证方法继续待确认。']})
    if mode=='explore':
        run.update(target='产品实习',target_status='provisional',assumptions=['教学案例假设用户要求直接判断；按访谈与原型证据暂定产品方向，真实使用须尊重用户意愿。'],
            role_options=[{'role':'产品实习','rationale':'访谈、问题归纳与原型交付有直接材料支持。','unknowns':'验证方法、偏好和可到岗条件待确认。','evidence_ids':['E2','E3']},
                          {'role':'运营支持','rationale':'记录核对与信息整理可构成执行类任务的迁移线索。','unknowns':'尚不能判断独立运营策略或业务结果；仅是备选方向。','evidence_ids':['E5']}])
        for option in run['role_options']:
            option.update(transfer_difficulty='需要核实已有任务与目标责任的差异。',next_action='确认偏好并检索目标岗位。',jd_source_ids=[],search_limitation='离线虚构教学案例，未检索真实岗位。')
    if mode!='jd':
        run['market_search']={'status':'not_needed','limitations':'离线虚构教学案例模拟用户明确只评估材料；不声称执行真实检索。','attempts':[]}
    write_json(root/'run.json',run)
    return root

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output-dir',required=True); p.add_argument('--mode',choices=['jd','direction','explore'],default='jd'); a=p.parse_args()
    print(build_example(a.output_dir,a.mode))
