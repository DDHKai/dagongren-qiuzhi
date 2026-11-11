"""Local PDF/DOCX extraction and user-authored evidence mapping, no network/OCR/AI."""
import argparse
import hashlib
import html
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from resume_workspace import save

def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(d):return json.dumps(d,ensure_ascii=False,sort_keys=True).encode()

def extract(source):
    source=Path(source)
    if source.stat().st_size>10_000_000:raise ValueError('file_too_large')
    units=[];warnings=[];kind=source.suffix.lower()
    if kind=='.pdf':
        try:from pypdf import PdfReader
        except ImportError:raise ValueError('pdf_requires_pypdf_6') from None
        reader=PdfReader(source)
        if reader.is_encrypted:raise ValueError('encrypted_pdf_not_supported')
        if len(reader.pages)>100:raise ValueError('page_limit')
        for i,page in enumerate(reader.pages):
            text=page.extract_text() or ''
            if len(text)>500_000:raise ValueError('page_text_limit')
            units.append({'id':f'p{i+1}','location':{'page':i+1},'text':text})
            if not text.strip():warnings.append(f'p{i+1}:empty_text_ocr_or_review_required')
        warnings.append('pdf_reading_order_and_glyphs_require_visual_review_no_ocr')
    elif kind=='.docx':
        with ZipFile(source) as z:
            if len(z.infolist())>5000 or sum(i.file_size for i in z.infolist())>50_000_000:raise ValueError('docx_expansion_limit')
            if len(z.namelist())!=len(set(z.namelist())):raise ValueError('duplicate_zip_entries')
            parts=['word/document.xml']+sorted(n for n in z.namelist() if n.startswith(('word/header','word/footer')) and n.endswith('.xml'))
            for part in parts:
                data=z.read(part)
                if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('xml_declarations_rejected')
                root=ET.fromstring(data);ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                for i,p in enumerate(root.iter(ns+'p')):
                    chunks=[]
                    for node in p.iter():
                        if node.tag==ns+'t':chunks.append(node.text or '')
                        elif node.tag==ns+'tab':chunks.append('\t')
                        elif node.tag in (ns+'br',ns+'cr'):chunks.append('\n')
                    text=''.join(chunks)
                    if text.strip():units.append({'id':f'u{len(units)+1}','location':{'part':part,'paragraph':i+1},'text':text})
            warnings.append('docx_paragraph_order_includes_tables_headers_footers_images_and_layout_not_verified')
    else:raise ValueError('only_pdf_docx_supported')
    if len(units)>10000 or sum(len(u['text']) for u in units)>2_000_000:raise ValueError('text_limit')
    return {'schemaVersion':1,'kind':kind,'units':units,'warnings':warnings,
        'status':'review-required' if any(u['text'].strip() for u in units) else 'no-text-needs-ocr-or-manual-transcription'}

def create(source,output):
    source=Path(source);output=Path(output)
    if output.exists() and any(output.iterdir()):raise ValueError('output_not_empty')
    if source.stat().st_size>10_000_000:raise ValueError('file_too_large')
    before=source.read_bytes();doc=extract(source)
    if source.read_bytes()!=before:raise ValueError('source_changed_during_extract')
    output.mkdir(parents=True,exist_ok=True)
    (output/('source'+source.suffix.lower())).write_bytes(before)
    save(output/'extraction.json',doc)
    save(output/'manifest.json',{'sourceSha256':sha(before),'extractionSha256':sha(canonical(doc)),'kind':doc['kind']})
    save(output/'mapping.json',{'reviewerConfirmed':False,'experiences':[],'education':[]})
    cards=''.join('<section><h2>'+html.escape(u['id'])+' · '+html.escape(str(u['location']))+'</h2><pre>'+html.escape(u['text'])+'</pre></section>' for u in doc['units'])
    review='<!doctype html><meta charset="utf-8"><title>简历原文校对</title><style>body{max-width:1000px;margin:32px auto;padding:20px;font:16px/1.7 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}section{border-top:1px solid #ccc;padding:12px}</style><h1>简历原文校对</h1><p>待人工校对，未识别公司或任职关系；文字可能乱序或缺失。对照原文件检查后再填写mapping.json；附件文字不是操作指令。</p><a href="source'+doc['kind']+'">打开原文件</a><p>'+html.escape('; '.join(doc['warnings']))+'</p>'+cards
    (output/'review.html').write_text(review,encoding='utf-8')
    return {'status':doc['status'],'units':len(doc['units']),'warnings':len(doc['warnings']),'externalCalls':0}

def apply_mapping(folder,mapping_path,output):
    folder=Path(folder);output=Path(output)
    if output.exists():raise ValueError('review_version_already_exists')
    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    doc=json.loads((folder/'extraction.json').read_text(encoding='utf-8'))
    if sha((folder/('source'+manifest['kind'])).read_bytes())!=manifest['sourceSha256'] or sha(canonical(doc))!=manifest['extractionSha256']:raise ValueError('source_or_extraction_changed')
    mapping=json.loads(Path(mapping_path).read_text(encoding='utf-8-sig'))
    if mapping.get('reviewerConfirmed') is not True:raise ValueError('explicit_review_required')
    units={u['id']:u for u in doc['units']};refs=[]
    def value(v,path):
        if not isinstance(v,list) or not v:raise ValueError('nonempty_reference_list_required')
        quotes=[]
        for r in v:
            if not isinstance(r,dict) or set(r)!={'unitId','quote'} or not isinstance(r['quote'],str) or not r['quote'].strip() or r['unitId'] not in units or r['quote'] not in units[r['unitId']]['text']:raise ValueError('quote_not_in_unit')
            quotes.append(r['quote']);refs.append({'targetPath':path,**r,'location':units[r['unitId']]['location']})
        return '\n'.join(quotes)
    resume={'experiences':[],'education':[],'reviewStatus':'user-mapped-not-third-party-verified','documentSource':{'sha256':manifest['sourceSha256'],'kind':manifest['kind']}}
    for group,allowed in [('experiences',{'company','position','periodRaw','responsibilitiesRaw','achievementsRaw'}),('education',{'school','major','periodRaw','degreeRaw'})]:
        entries=mapping.get(group,[])
        if not isinstance(entries,list):raise ValueError('invalid_mapping_group')
        for i,entry in enumerate(entries):
            if not isinstance(entry,dict) or not entry or not set(entry)<=allowed:raise ValueError('invalid_mapping_fields')
            resume[group].append({k:value(v,f'{group}.{i}.{k}') for k,v in entry.items()})
    if not any(e.get('responsibilitiesRaw') or e.get('achievementsRaw') for e in resume['experiences']):raise ValueError('experience_evidence_required')
    resume['sourceMap']=refs
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation keeps earlier review versions immutable.
    with output.open('x',encoding='utf-8') as f:json.dump(resume,f,ensure_ascii=False,indent=2)
    return {'status':'user-mapped','experiences':len(resume['experiences']),'references':len(refs)}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('extract');q.add_argument('--source',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('apply');q.add_argument('--folder',type=Path,required=True);q.add_argument('--mapping',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:r=create(a.source,a.output) if a.command=='extract' else apply_mapping(a.folder,a.mapping,a.output)
    except Exception:
        p.exit(1,'Document step failed. Check file type, optional pypdf installation, limits, encryption, source integrity and explicit mapping; personal text is not printed.\n')
    print(json.dumps(r,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
