import datetime
import logging
import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# ==========================================
# CONFIGURAÇÃO E FORMATALIZAÇÃO DE LOGS
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s",
    handlers=[
        logging.FileHandler("castock_system.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CAStock")

# ==========================================
# CONFIGURAÇÃO DE BANCO DE DADOS (SQLite / PostgreSQL)
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./castock.db")

# Ajuste especial para Neon/PostgreSQL (postgres:// -> postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Ajuste especial para caminhos em volumes persistentes de SQLite
if DATABASE_URL.startswith("sqlite:////"):
    db_dir = os.path.dirname(DATABASE_URL.replace("sqlite:////", "/"))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

# Conexão de Engine híbrida (SQLite precisa de check_same_thread, Postgres não)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()

# ==========================================
# MODELOS DE DADOS DO BANCO (SQLAlchemy ORM)
# ==========================================
class Product(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    preco = Column(Float, nullable=False)
    estoque = Column(Integer, nullable=False)
    vendas = relationship("Sale", back_populates="produto", cascade="all, delete-orphan")

class Sale(Base):
    __tablename__ = "vendas"
    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False)
    total = Column(Float, nullable=False)
    data_venda = Column(DateTime, default=datetime.datetime.now)
    
    produto = relationship("Product", back_populates="vendas")

# Criar tabelas se não existirem no SQLite/Postgres
Base.metadata.create_all(bind=engine)
db_name = "PostgreSQL (Neon)" if "postgresql" in engine.url.drivername else "SQLite"
logger.info(f"Banco de Dados: Tabelas de produtos e vendas carregadas/inicializadas com sucesso no {db_name}.")

# Semear banco de dados com produtos de teste padrão se a tabela estiver vazia
def seed_produtos():
    db = SessionLocal()
    try:
        # Verificar se existem produtos
        count = db.query(Product).count()
        if count == 0:
            p1 = Product(nome="Refrigerante Coca-Cola Lata", preco=5.00, estoque=30)
            p2 = Product(nome="Salgado Assado de Frango", preco=6.50, estoque=15)
            p3 = Product(nome="Barra de Chocolate Hersheys", preco=4.50, estoque=20)
            db.add_all([p1, p2, p3])
            db.commit()
            logger.info(f"Semeadura de Banco: 3 produtos padrão foram semeados com sucesso no {db_name}.")
    except Exception as e:
        logger.error(f"Erro ao semear produtos: {e}", exc_info=True)
    finally:
        db.close()

seed_produtos()

# Dependência para obter a sessão do DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# ESQUEMAS DE VALIDAÇÃO DE DADOS (Pydantic)
# ==========================================
class ProductCreate(BaseModel):
    nome: str = Field(..., min_length=1)
    preco: float = Field(..., gt=0)
    estoque: int = Field(..., ge=0)

class ProductResponse(BaseModel):
    id: int
    nome: str
    preco: float
    estoque: int

    class Config:
        from_attributes = True

class SaleCreate(BaseModel):
    produto_id: int
    quantidade: int = Field(..., gt=0)

class SaleResponse(BaseModel):
    id: int
    produto_id: int
    produto_nome: str
    quantidade: int
    total: float
    data_venda: datetime.datetime

    class Config:
        from_attributes = True

# ==========================================
# INICIALIZAÇÃO E ROTAS DA API FASTAPI
# ==========================================
app = FastAPI(title="CAStock API", description="CRUD básico de estoque do Centro Acadêmico", version="1.0.0")

# CORS para desenvolvimento
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- ENDPOINTS DE PRODUTOS -----------------
@app.get("/api/produtos", response_model=List[ProductResponse])
def listar_produtos(db: Session = Depends(get_db)):
    produtos = db.query(Product).all()
    return produtos

@app.post("/api/produtos", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def cadastrar_produto(product_data: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(
        nome=product_data.nome,
        preco=product_data.preco,
        estoque=product_data.estoque
    )
    db.add(new_product)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar produto no banco: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao salvar produto no banco de dados."
        )
    
    logger.info(f"Estoque: Novo produto cadastrado: '{new_product.nome}' (Preço: R$ {new_product.preco}, Estoque Inicial: {new_product.estoque})")
    return new_product

@app.delete("/api/produtos/{product_id}", status_code=status.HTTP_200_OK)
def excluir_produto(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        logger.warning(f"Estoque: Tentativa de excluir produto inexistente (ID: {product_id})")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado."
        )
    
    nome_produto = product.nome
    db.delete(product)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao excluir produto (ID: {product_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao excluir produto no banco de dados."
        )
    
    logger.info(f"Estoque: Produto '{nome_produto}' (ID: {product_id}) excluído com sucesso.")
    return {"message": f"Produto '{nome_produto}' excluído com sucesso."}

@app.post("/api/produtos/{product_id}/adicionar-estoque", response_model=ProductResponse)
def adicionar_estoque(product_id: int, quantidade: int, db: Session = Depends(get_db)):
    if quantidade <= 0:
        logger.warning(f"Estoque: Tentativa de adicionar quantidade inválida ({quantidade}) ao estoque (ID: {product_id})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A quantidade a ser adicionada deve ser maior que zero."
        )
        
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        logger.warning(f"Estoque: Tentativa de adicionar estoque a produto inexistente (ID: {product_id})")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado."
        )
    
    product.estoque += quantidade
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao adicionar estoque ao produto (ID: {product_id}): {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar o estoque no banco de dados."
        )
    
    logger.info(f"Estoque: Adicionadas {quantidade} un. ao produto '{product.nome}' (Novo Estoque: {product.estoque})")
    return product

# ----------------- ENDPOINTS DE VENDAS -----------------
@app.post("/api/vendas", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def registrar_venda(sale_data: SaleCreate, db: Session = Depends(get_db)):
    # Buscar o produto
    product = db.query(Product).filter(Product.id == sale_data.produto_id).first()
    if not product:
        logger.warning(f"Vendas: Tentativa de venda de produto inexistente (ID: {sale_data.produto_id})")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado."
        )
    
    # Verificar estoque
    if product.estoque < sale_data.quantidade:
        logger.warning(f"Estoque: Tentativa de venda de '{product.nome}' com estoque insuficiente (Qtd Solicitada: {sale_data.quantidade}, Disponível: {product.estoque})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estoque insuficiente. Disponível: {product.estoque} unidades."
        )
    
    # Transação: Atualizar estoque e calcular total
    total_venda = product.preco * sale_data.quantidade
    product.estoque -= sale_data.quantidade
    
    # Registrar a venda
    new_sale = Sale(
        produto_id=sale_data.produto_id,
        quantidade=sale_data.quantidade,
        total=total_venda,
        data_venda=datetime.datetime.now()
    )
    
    db.add(new_sale)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar venda no banco: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao salvar venda no banco de dados."
        )
    
    logger.info(f"Vendas: Registrada venda de {new_sale.quantidade} un. de '{product.nome}' (Total: R$ {new_sale.total})")
    return SaleResponse(
        id=new_sale.id,
        produto_id=new_sale.produto_id,
        produto_nome=product.nome,
        quantidade=new_sale.quantidade,
        total=new_sale.total,
        data_venda=new_sale.data_venda
    )

@app.get("/api/vendas", response_model=List[SaleResponse])
def listar_vendas(db: Session = Depends(get_db)):
    vendas = db.query(Sale).join(Product).order_by(Sale.data_venda.desc()).all()
    
    response = []
    for venda in vendas:
        response.append(
            SaleResponse(
                id=venda.id,
                produto_id=venda.produto_id,
                produto_nome=venda.produto.nome,
                quantidade=venda.quantidade,
                total=venda.total,
                data_venda=venda.data_venda
            )
        )
    return response

# ==========================================
# FRONT-END (SERVIDOR DE ARQUIVOS ESTÁTICOS)
# ==========================================
@app.get("/")
def read_root():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "CAStock Backend rodando! Pasta 'static/' não encontrada."}

# Criar pasta static se não existir
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/", StaticFiles(directory="static"), name="static")

# Execução com uvicorn
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
