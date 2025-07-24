from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import tempfile, os, logging, shutil, gc
from typing import Dict, Any

# Logging detalhado
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Pasta para imagens
IMAGES_DIR = "/tmp/docling_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# Import Docling
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, granite_picture_description
    DOCLING_OK = True
    logger.info("✅ Docling + Granite carregado")
except ImportError as e:
    DOCLING_OK = False
    logger.error(f"❌ Erro Docling: {e}")

# FastAPI
app = FastAPI(title="Docling Granite API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/")
def status():
    return {"status": "ok", "docling": DOCLING_OK, "modelo": "granite-vision", "porta": 9000}

# Função COMPLETA com Granite VLM
def processar_documento_granite(arquivo_path: str) -> Dict[str, Any]:
    if not DOCLING_OK:
        raise HTTPException(status_code=500, detail="Docling não disponível")
    
    try:
        logger.info("🔥 Processando com GRANITE VLM ativado...")
        
        # Limpar memória antes de começar
        gc.collect()
        
        # Configuração OTIMIZADA para Granite
        options = PdfPipelineOptions()
        
        # Configurações básicas
        options.do_ocr = True
        options.do_table_structure = True
        options.generate_picture_images = True
        options.images_scale = 1  # Resolução controlada
        
        # GRANITE VLM ATIVADO 🔥
        options.do_picture_description = True
        options.picture_description_options = granite_picture_description
        
        logger.info("✅ Granite Vision configurado!")
        logger.info(f"   - OCR: {options.do_ocr}")
        logger.info(f"   - Tabelas: {options.do_table_structure}")
        logger.info(f"   - Imagens: {options.generate_picture_images}")
        logger.info(f"   - Granite VLM: {options.do_picture_description}")
        logger.info(f"   - Escala: {options.images_scale}")
        
        # Converter
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        
        logger.info("🔄 Executando conversão com Granite...")
        resultado = converter.convert(arquivo_path)
        logger.info("✅ Conversão Granite concluída!")
        
        doc = resultado.document
        
        # Extrair dados
        elementos = []
        texto_completo = []
        contador_granite = 0
        
        # TEXTOS
        logger.info("📝 Processando textos...")
        for i, texto in enumerate(doc.texts):
            if texto.text and texto.text.strip():
                # Página via prov
                pagina = 1
                if hasattr(texto, 'prov') and texto.prov and len(texto.prov) > 0:
                    pagina = texto.prov[0].page_no
                
                elementos.append({
                    "tipo": "texto",
                    "conteudo": texto.text,
                    "pagina": pagina
                })
                texto_completo.append(texto.text)
                
                if i % 50 == 0:
                    logger.info(f"Processados {i} textos...")
        
        logger.info(f"✅ {len([e for e in elementos if e['tipo'] == 'texto'])} textos extraídos")
        
        # TABELAS
        logger.info("📊 Processando tabelas...")
        for i, tabela in enumerate(doc.tables):
            try:
                pagina = 1
                if hasattr(tabela, 'prov') and tabela.prov and len(tabela.prov) > 0:
                    pagina = tabela.prov[0].page_no
                
                elementos.append({
                    "tipo": "tabela",
                    "dados": [[getattr(cell, 'text', str(cell)) for cell in row] for row in tabela.data],
                    "pagina": pagina
                })
                logger.info(f"Tabela {i+1} processada")
            except Exception as e:
                logger.warning(f"Erro na tabela {i}: {e}")
        
        # IMAGENS COM GRANITE VLM 🎯
        logger.info("🖼️ Processando imagens com Granite Vision...")
        
        # Debug: total de imagens
        total_pics = len(doc.pictures)
        logger.info(f"📷 Total de imagens encontradas: {total_pics}")
        
        for i, img in enumerate(doc.pictures):
            try:
                logger.info(f"🔍 Analisando imagem {i+1}/{total_pics}...")
                
                # Página via prov
                pagina = 1
                if hasattr(img, 'prov') and img.prov and len(img.prov) > 0:
                    pagina = img.prov[0].page_no
                
                # Salvar imagem
                img_url = None
                if img.image and hasattr(img.image, 'uri') and img.image.uri and os.path.exists(img.image.uri):
                    nome_arquivo = f"granite_img_p{pagina}_{i}.png"
                    caminho_destino = os.path.join(IMAGES_DIR, nome_arquivo)
                    shutil.copy(img.image.uri, caminho_destino)
                    img_url = f"/images/{nome_arquivo}"
                    logger.info(f"🖼️ Imagem {i+1} salva: {nome_arquivo}")
                else:
                    logger.warning(f"⚠️ Imagem {i+1} - URI inválida ou arquivo não existe")
                
                # EXTRAIR DESCRIÇÕES GRANITE 🔥
                descricoes_granite = []
                
                # Debug das anotações
                if hasattr(img, 'annotations'):
                    if img.annotations and len(img.annotations) > 0:
                        logger.info(f"📝 Imagem {i+1} tem {len(img.annotations)} anotações")
                        
                        for j, annotation in enumerate(img.annotations):
                            try:
                                # Verificar propriedades da anotação
                                ann_kind = getattr(annotation, 'kind', None)
                                ann_text = getattr(annotation, 'text', None)
                                
                                logger.info(f"   Anotação {j+1}: kind='{ann_kind}', text_len={len(str(ann_text)) if ann_text else 0}")
                                
                                # Verificar se é descrição do Granite
                                if ann_kind == 'description' and ann_text and str(ann_text).strip():
                                    desc_text = str(ann_text).strip()
                                    
                                    descricoes_granite.append({
                                        "texto": desc_text,
                                        "modelo": "granite-vision",
                                        "confianca": "alta"
                                    })
                                    contador_granite += 1
                                    
                                    # Adicionar ao texto completo
                                    texto_completo.append(f"[Granite Vision - Página {pagina}, Imagem {i+1}]: {desc_text}")
                                    
                                    logger.info(f"✅ Granite descrição {j+1}: {desc_text[:100]}...")
                                else:
                                    logger.info(f"   ⏭️ Anotação {j+1} ignorada (não é descrição Granite)")
                                    
                            except Exception as e:
                                logger.warning(f"Erro processando anotação {j}: {e}")
                    else:
                        logger.info(f"📝 Imagem {i+1} não tem anotações")
                else:
                    logger.info(f"📝 Imagem {i+1} não tem atributo 'annotations'")
                
                # Elemento da imagem
                elementos.append({
                    "tipo": "imagem",
                    "url": img_url,
                    "legenda": getattr(img, "caption", "") or "",
                    "descricoes_granite": descricoes_granite,
                    "pagina": pagina,
                    "total_descricoes": len(descricoes_granite)
                })
                
                logger.info(f"✅ Imagem {i+1} processada com {len(descricoes_granite)} descrições Granite")
                
            except Exception as e:
                logger.error(f"❌ Erro processando imagem {i}: {e}")
                # Adicionar imagem sem descrição se der erro
                elementos.append({
                    "tipo": "imagem",
                    "url": None,
                    "legenda": "",
                    "descricoes_granite": [],
                    "pagina": pagina if 'pagina' in locals() else 1,
                    "erro": str(e)
                })
        
        # Texto final
        total_texto = "\n".join(texto_completo)
        
        if not total_texto.strip():
            total_texto = "Nenhum texto foi extraído do documento."
            logger.warning("⚠️ Nenhum texto extraído")
        
        # Estatísticas detalhadas
        total_textos = len([e for e in elementos if e['tipo'] == 'texto'])
        total_tabelas = len([e for e in elementos if e['tipo'] == 'tabela'])
        total_imagens = len([e for e in elementos if e['tipo'] == 'imagem'])
        
        # Resultado final
        resultado_final = {
            "elementos": elementos,
            "texto": total_texto,
            "resumo": {
                "total_elementos": len(elementos),
                "total_textos": total_textos,
                "total_tabelas": total_tabelas,
                "total_imagens": total_imagens,
                "descricoes_granite": contador_granite,
                "modelo": "granite-vision",
                "status": "sucesso_com_granite",
                "granite_ativo": True,
                "taxa_sucesso": f"{contador_granite}/{total_imagens}" if total_imagens > 0 else "0/0"
            }
        }
        
        logger.info(f"🎯 GRANITE SUCESSO TOTAL: {contador_granite} descrições geradas!")
        logger.info(f"📊 Elementos: {len(elementos)} | Imagens: {total_imagens}")
        logger.info(f"🔥 Taxa Granite: {contador_granite}/{total_imagens}")
        
        return resultado_final
        
    except Exception as e:
        logger.error(f"❌ ERRO no processamento Granite: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Tentar fallback sem VLM se for erro de memória
        if "buffer size" in str(e).lower() or "memory" in str(e).lower():
            logger.warning("🔄 Erro de memória detectado, tentando fallback sem VLM...")
            return processar_documento_fallback(arquivo_path)
        else:
            raise HTTPException(status_code=500, detail=f"Erro Granite: {str(e)}")

# Função FALLBACK sem VLM
def processar_documento_fallback(arquivo_path: str) -> Dict[str, Any]:
    try:
        logger.info("⚠️ Executando fallback SEM VLM...")
        
        # Configuração mínima sem VLM
        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        options.generate_picture_images = True
        options.images_scale = 1
        options.do_picture_description = False  # SEM VLM
        
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
        
        resultado = converter.convert(arquivo_path)
        doc = resultado.document
        
        # Mesmo processamento mas sem descrições VLM
        elementos = []
        texto_completo = []
        
        # Textos
        for texto in doc.texts:
            if texto.text and texto.text.strip():
                pagina = 1
                if hasattr(texto, 'prov') and texto.prov and len(texto.prov) > 0:
                    pagina = texto.prov[0].page_no
                
                elementos.append({
                    "tipo": "texto",
                    "conteudo": texto.text,
                    "pagina": pagina
                })
                texto_completo.append(texto.text)
        
        # Tabelas
        for tabela in doc.tables:
            try:
                pagina = 1
                if hasattr(tabela, 'prov') and tabela.prov and len(tabela.prov) > 0:
                    pagina = tabela.prov[0].page_no
                
                elementos.append({
                    "tipo": "tabela",
                    "dados": [[getattr(cell, 'text', str(cell)) for cell in row] for row in tabela.data],
                    "pagina": pagina
                })
            except:
                pass
        
        # Imagens sem descrições
        for i, img in enumerate(doc.pictures):
            try:
                pagina = 1
                if hasattr(img, 'prov') and img.prov and len(img.prov) > 0:
                    pagina = img.prov[0].page_no
                
                img_url = None
                if img.image and hasattr(img.image, 'uri') and img.image.uri and os.path.exists(img.image.uri):
                    nome_arquivo = f"fallback_img_p{pagina}_{i}.png"
                    caminho_destino = os.path.join(IMAGES_DIR, nome_arquivo)
                    shutil.copy(img.image.uri, caminho_destino)
                    img_url = f"/images/{nome_arquivo}"
                
                elementos.append({
                    "tipo": "imagem",
                    "url": img_url,
                    "legenda": getattr(img, "caption", "") or "",
                    "descricoes_granite": [],  # Vazio no fallback
                    "pagina": pagina
                })
            except:
                pass
        
        return {
            "elementos": elementos,
            "texto": "\n".join(texto_completo),
            "resumo": {
                "total_elementos": len(elementos),
                "descricoes_granite": 0,
                "modelo": "fallback-sem-vlm",
                "status": "sucesso_fallback"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Erro até no fallback: {e}")
        return {
            "elementos": [],
            "texto": f"Erro crítico: {str(e)}",
            "resumo": {
                "total_elementos": 0,
                "descricoes_granite": 0,
                "modelo": "erro",
                "status": "falha_total"
            }
        }

# ENDPOINT PRINCIPAL
@app.post("/convert")
async def converter_documento(file: UploadFile = File(...)):
    logger.info(f"📄 RECEBIDO: {file.filename}")
    
    # Validações
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos")
    
    # Ler arquivo
    conteudo = await file.read()
    tamanho_mb = len(conteudo) / (1024 * 1024)
    
    # Limite de tamanho para Granite
    if tamanho_mb > 25:  # Limite conservador
        raise HTTPException(status_code=400, detail=f"Arquivo muito grande para Granite: {tamanho_mb:.1f}MB. Máximo: 25MB")
    
    logger.info(f"📁 Arquivo válido: {len(conteudo)} bytes ({tamanho_mb:.1f}MB)")
    
    # Salvar arquivo temporário
    arquivo_temp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(conteudo)
            arquivo_temp = tmp.name
        
        logger.info(f"💾 Arquivo salvo temporariamente: {arquivo_temp}")
        
        # PROCESSAR COM GRANITE 🔥
        resultado = processar_documento_granite(arquivo_temp)
        
        logger.info("✅ Processamento concluído com sucesso!")
        return JSONResponse(content=resultado)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ ERRO GERAL: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")
    
    finally:
        # Limpar arquivo temporário
        if arquivo_temp and os.path.exists(arquivo_temp):
            os.unlink(arquivo_temp)
            logger.info("🗑️ Arquivo temporário removido")

# Endpoints adicionais
@app.post("/test-granite")
async def testar_granite(file: UploadFile = File(...)):
    """Endpoint específico para testar Granite"""
    logger.info("🧪 TESTE GRANITE ESPECÍFICO")
    return await converter_documento(file)

@app.get("/test")
def teste():
    return {
        "status": "Granite API OK", 
        "docling": DOCLING_OK, 
        "modelo": "granite-vision",
        "endpoint_principal": "/convert",
        "granite_ativo": True,
        "porta": 9000
    }

@app.get("/status")
def status_detalhado():
    return {
        "docling_disponivel": DOCLING_OK,
        "granite_ativo": True,
        "porta": 9000,
        "endpoints": {
            "principal": "/convert",
            "teste": "/test-granite",
            "status": "/test"
        },
        "limites": {
            "tamanho_max": "25MB",
            "formatos": ["PDF"]
        },
        "recursos": {
            "vlm": "granite-vision",
            "ocr": True,
            "tabelas": True,
            "imagens": True
        }
    }

if __name__ == "__main__":
    logger.info("🚀 Servidor Docling Granite iniciado na PORTA 9000!")
    logger.info("🔥 Granite Vision ATIVO!")
    logger.info("📋 Endpoints:")
    logger.info("  - POST http://localhost:9000/convert (principal)")
    logger.info("  - POST http://localhost:9000/test-granite (teste)")
    logger.info("  - GET http://localhost:9000/test (status)")
    logger.info("  - GET http://localhost:9000/status (detalhes)")
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)