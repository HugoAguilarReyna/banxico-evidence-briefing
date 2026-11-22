"""Compara recuperación léxica con BM25, sin llamar a un modelo ni a la red.

PYTHONPATH=src python research/evaluar_recuperacion.py
Los errores se publican; no se modifica el conjunto para mejorar la puntuación.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import math
import statistics
import time
from app.rag_banxico.service import puntuar, terminos

ROOT=Path(__file__).resolve().parents[1]

def bm25(question,chunks):
    docs=[Counter(terminos(c['heading']+' '+c['content']+' '+' '.join(c.get('keywords',[])))) for c in chunks]
    lengths=[sum(d.values()) for d in docs]
    avg=sum(lengths)/len(docs)
    scores=[]
    for c,doc,length in zip(chunks,docs,lengths):
        score=0
        for word in set(terminos(question)):
            tf=doc[word]
            df=sum(word in d for d in docs)
            idf=math.log(1+(len(docs)-df+.5)/(df+.5))
            score+=idf*tf*2.2/(tf+1.2*(.25+.75*length/avg))
        if score>0: scores.append((score,c['chunk_id']))
    return [id for _,id in sorted(scores,key=lambda x:(-x[0],x[1]))[:3]]

def main():
    corpus_path=ROOT/'web/corpus.json'
    questions_path=ROOT/'research/preguntas.json'
    chunks=json.loads(corpus_path.read_text(encoding='utf-8'))['chunks']
    cases=json.loads(questions_path.read_text(encoding='utf-8'))['casos']
    engines={'lexico':lambda q:[c['chunk_id'] for c in puntuar(q,chunks)],'bm25':lambda q:bm25(q,chunks)}
    result={
        'alcance':'Diagnóstico local de recuperación; no evalúa generación LLM ni validez de las fuentes originales.',
        'corpus_sha256':hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        'preguntas_sha256':hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        'casos':len(cases),'proveedor_llm':'no ejecutado','coste_llm_usd':0,'motores':{},
    }
    for name,engine in engines.items():
        rows=[]
        for case in cases:
            start=time.perf_counter()
            ids=engine(case['pregunta'])
            ms=(time.perf_counter()-start)*1000
            ok=case['esperado'] in ids if case['esperado'] else not ids
            rows.append({**case,'recuperados':ids,'correcto':ok,'latencia_ms':round(ms,3)})
        positive=[r for r in rows if r['esperado']]
        negative=[r for r in rows if not r['esperado']]
        latencies=sorted(r['latencia_ms'] for r in rows)
        result['motores'][name]={
            'hit_rate_at_3':sum(r['correcto'] for r in positive)/len(positive),
            'abstencion_correcta':sum(r['correcto'] for r in negative)/len(negative),
            'fuera_de_alcance_con_coincidencias':sum(not r['correcto'] for r in negative),
            'latencia_p50_ms':statistics.median(latencies),'latencia_p95_ms':latencies[math.ceil(.95*len(latencies))-1],
            'filas':rows,
        }
    path=ROOT/'research/resultado_recuperacion.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({name:{k:v for k,v in m.items() if k!='filas'} for name,m in result['motores'].items()},ensure_ascii=False))

if __name__=='__main__': main()
