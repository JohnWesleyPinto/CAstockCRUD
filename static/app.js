/* ==========================================================================
   CAStock - Front-End Core Client Logic (Vanilla JS SPA)
   ========================================================================== */

// --- ESTADO GLOBAL DA APLICAÇÃO ---
const state = {
  products: [],
  sales: []
};

// --- CONFIGURAÇÃO DA API ---
// Em ambiente local, consome a API local (/api).
// Em produção (hospedado na Vercel), consome a API do Render.
// IMPORTANTE: Substitua a URL abaixo pela URL real que o Render gerar para o seu Web Service!
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? '/api'
  : 'https://castock-api.onrender.com';


// Headers comuns (Content-Type JSON padrão)
function getHeaders() {
  return {
    'Content-Type': 'application/json'
  };
}

// Auxiliar robusto para realizar requisições HTTP e tratar respostas de erro detalhadamente
async function safeFetch(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get('content-type');

  if (response.ok) {
    if (contentType && contentType.includes('application/json')) {
      return await response.json();
    }
    return null;
  } else {
    if (contentType && contentType.includes('application/json')) {
      const errData = await response.json();
      throw new Error(getErrorMessage(errData, `Erro ${response.status}`));
    } else {
      const errText = await response.text();
      // Remove tags HTML se o erro for um HTML do Uvicorn/Servidor e pega o texto limpo
      const cleanText = errText.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim().substring(0, 120);
      throw new Error(`Erro ${response.status}: ${cleanText || response.statusText}`);
    }
  }
}

// --- SISTEMA PREMIUM DE NOTIFICAÇÕES (TOASTS) ---
function showToast(title, message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  // Definição de Ícone SVG conforme tipo
  let iconSvg = '';
  if (type === 'success') {
    iconSvg = `<svg class="toast-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
  } else if (type === 'error') {
    iconSvg = `<svg class="toast-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;
  } else {
    iconSvg = `<svg class="toast-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;
  }

  toast.innerHTML = `
    ${iconSvg}
    <div class="toast-body">
      <span class="toast-title">${title}</span>
      <span class="toast-message">${message}</span>
    </div>
  `;

  container.appendChild(toast);

  // Trigger de animação de entrada
  setTimeout(() => toast.classList.add('show'), 50);

  // Auto-destruição após 4 segundos
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

// Auxiliar para extrair de forma robusta e amigável mensagens de erro vindas do back-end
function getErrorMessage(data, defaultMsg) {
  if (!data) return defaultMsg;
  if (typeof data === 'string') return data;
  if (data.detail) {
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      // Tratar array de erros de validação do Pydantic/FastAPI
      return data.detail.map(err => {
        const field = err.loc ? err.loc[err.loc.length - 1] : '';
        const msg = err.msg || 'erro de validação';
        return field ? `${field}: ${msg}` : msg;
      }).join(', ');
    }
    if (typeof data.detail === 'object') {
      return JSON.stringify(data.detail);
    }
  }
  if (data.message) return data.message;
  return defaultMsg;
}

// --- ATUALIZAR CONTEÚDO DO PAINEL ---
async function refreshDashboardData() {
  await Promise.all([
    loadProducts(),
    loadSales()
  ]);
}

// --- PRODUTOS ---
async function loadProducts() {
  try {
    state.products = await safeFetch(`${API_BASE}/produtos`);
    console.log('CAStock Debug: Produtos carregados da API:', state.products);
    renderProductsTable();
    renderProductSelectDropdown();
    renderSalesSelectionTable();
  } catch (error) {
    console.error('CAStock Debug: Erro ao carregar produtos:', error);
    showToast('Erro de Inventário', error.message, 'error');
  }
}

function renderProductsTable() {
  const tbody = document.getElementById('products-table-body');
  if (!tbody) return;

  if (state.products.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">Nenhum produto cadastrado.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.products.map(prod => {
    let statusBadge = '';

    if (prod.estoque === 0) {
      statusBadge = '<span class="badge badge-danger">Esgotado</span>';
    } else if (prod.estoque <= 5) {
      statusBadge = `<span class="badge badge-warning" title="Apenas ${prod.estoque} restantes!">Estoque Baixo</span>`;
    } else {
      statusBadge = '<span class="badge badge-success">Disponível</span>';
    }

    const formattedPrice = prod.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

    return `
      <tr class="product-row" data-name="${prod.nome.toLowerCase()}">
        <td class="font-semibold">${escapeHTML(prod.nome)}</td>
        <td class="text-right font-medium">${formattedPrice}</td>
        <td class="text-center font-bold">${prod.estoque}</td>
        <td class="text-center">${statusBadge}</td>
        <td class="text-center">
          <button type="button" class="btn-restock" onclick="handleRestockProduct(${prod.id}, '${escapeHTML(prod.nome)}')" title="Adicionar estoque">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
          <button type="button" class="btn-delete" onclick="handleDeleteProduct(${prod.id}, '${escapeHTML(prod.nome)}')" title="Excluir produto">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function filterProductsTable() {
  const query = document.getElementById('search-products').value.toLowerCase().trim();
  const rows = document.querySelectorAll('#products-table-body .product-row');

  rows.forEach(row => {
    const name = row.getAttribute('data-name');
    if (name.includes(query)) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

function renderProductSelectDropdown() {
  const select = document.getElementById('sale-product-select');
  if (!select) {
    console.log('CAStock Debug: Elemento "#sale-product-select" não encontrado no DOM desta página.');
    return;
  }

  const availableProducts = state.products.filter(prod => prod.estoque > 0);
  console.log('CAStock Debug: Produtos com estoque > 0:', availableProducts);

  if (availableProducts.length === 0) {
    select.innerHTML = '<option value="" disabled selected>Nenhum produto disponível no estoque</option>';
    calculateSaleTotal();
    return;
  }

  const options = availableProducts.map(prod => {
    const nameWithStock = `${prod.nome} (${prod.estoque} un - R$ ${prod.preco.toFixed(2)})`;
    return `<option value="${prod.id}" data-price="${prod.preco}" data-stock="${prod.estoque}">${escapeHTML(nameWithStock)}</option>`;
  }).join('');

  select.innerHTML = '<option value="" disabled selected>Escolha um produto para venda...</option>' + options;
  console.log('CAStock Debug: Dropdown de vendas renderizado com sucesso.');
  calculateSaleTotal();
}

// --- NOVO FLUXO: CAIXA REGISTRADORA / PDV MULTI-ITENS ---
function renderSalesSelectionTable() {
  const tbody = document.getElementById('sales-selection-body');
  if (!tbody) {
    console.log('CAStock Debug: Elemento "#sales-selection-body" não encontrado no DOM desta página.');
    return;
  }

  // Filtrar apenas produtos com estoque > 0
  const availableProducts = state.products.filter(prod => prod.estoque > 0);

  if (availableProducts.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">Nenhum produto disponível no estoque para venda.</td></tr>`;
    calculatePOSTotal();
    return;
  }

  tbody.innerHTML = availableProducts.map(prod => {
    const formattedPrice = prod.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

    return `
      <tr class="pos-row" data-id="${prod.id}" data-price="${prod.preco}">
        <td class="font-semibold">${escapeHTML(prod.nome)}</td>
        <td class="text-right font-medium">${formattedPrice}</td>
        <td class="text-center font-bold text-wine">${prod.estoque} un</td>
        <td class="text-center">
          <div class="qty-counter" id="counter-${prod.id}">
            <button type="button" class="btn-qty" onclick="changePOSQty(${prod.id}, -1, ${prod.estoque})">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>
            <input type="number" class="qty-input" id="qty-${prod.id}" min="0" max="${prod.estoque}" value="0" oninput="validatePOSQty(${prod.id}, ${prod.estoque})">
            <button type="button" class="btn-qty" onclick="changePOSQty(${prod.id}, 1, ${prod.estoque})">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  console.log('CAStock Debug: Tabela do PDV renderizada com sucesso.');
  calculatePOSTotal();
}

function changePOSQty(prodId, step, maxStock) {
  const input = document.getElementById(`qty-${prodId}`);
  if (!input) return;

  let val = parseInt(input.value) || 0;
  val = Math.max(0, Math.min(maxStock, val + step));
  input.value = val;

  validatePOSQty(prodId, maxStock);
}

function validatePOSQty(prodId, maxStock) {
  const input = document.getElementById(`qty-${prodId}`);
  const counter = document.getElementById(`counter-${prodId}`);
  if (!input || !counter) return;

  let val = parseInt(input.value) || 0;
  if (val < 0) val = 0;
  if (val > maxStock) {
    val = maxStock;
    input.setCustomValidity(`Estoque máximo disponível: ${maxStock}`);
    input.reportValidity();
  } else {
    input.setCustomValidity('');
  }
  input.value = val;

  // Destaca a borda se a quantidade for maior que zero
  if (val > 0) {
    counter.classList.add('has-qty');
  } else {
    counter.classList.remove('has-qty');
  }

  calculatePOSTotal();
}

function calculatePOSTotal() {
  const rows = document.querySelectorAll('#sales-selection-body .pos-row');
  const totalDisplay = document.getElementById('checkout-total-value');
  if (!totalDisplay) return;

  let total = 0;

  rows.forEach(row => {
    const prodId = row.getAttribute('data-id');
    const price = parseFloat(row.getAttribute('data-price')) || 0;
    const input = document.getElementById(`qty-${prodId}`);
    const qty = input ? (parseInt(input.value) || 0) : 0;

    total += price * qty;
  });

  totalDisplay.textContent = total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

async function submitPOSSale() {
  const btn = document.getElementById('btn-checkout-submit');
  if (!btn) return;

  const rows = document.querySelectorAll('#sales-selection-body .pos-row');
  const salesToCreate = [];

  rows.forEach(row => {
    const produto_id = parseInt(row.getAttribute('data-id'));
    const input = document.getElementById(`qty-${produto_id}`);
    const quantidade = input ? (parseInt(input.value) || 0) : 0;

    if (quantidade > 0) {
      salesToCreate.push({ produto_id, quantidade });
    }
  });

  if (salesToCreate.length === 0) {
    showToast('Caixa Vazio', 'Selecione a quantidade de pelo menos um produto para registrar a venda.', 'warning');
    return;
  }

  try {
    btn.disabled = true;
    btn.innerHTML = '<span>Processando...</span>';

    // Dispara todas as requisições em paralelo via Promise.all
    const promises = salesToCreate.map(sale =>
      safeFetch(`${API_BASE}/vendas`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(sale)
      })
    );

    const results = await Promise.all(promises);

    // Calcula o total consolidado de itens vendidos
    const totalItems = results.reduce((acc, cur) => acc + cur.quantidade, 0);
    showToast('Venda Efetuada!', `Caixa fechado com sucesso! ${totalItems} itens registrados.`, 'success');

    // Recarrega todos os dados
    await refreshDashboardData();
  } catch (error) {
    showToast('Erro no Caixa', error.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <span>Confirmar e Registrar Venda</span>
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    `;
  }
}

async function handleCreateProduct(event) {
  event.preventDefault();
  const nome = document.getElementById('prod-name').value;
  const preco = parseFloat(document.getElementById('prod-price').value);
  const estoque = parseInt(document.getElementById('prod-stock').value);
  const btn = document.getElementById('btn-product-submit');

  try {
    btn.disabled = true;
    const data = await safeFetch(`${API_BASE}/produtos`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ nome, preco, estoque })
    });

    showToast('Produto Cadastrado', `"${data.nome}" adicionado com sucesso!`, 'success');
    closeNewProductModal();
    document.getElementById('new-product-form').reset();
    await refreshDashboardData();
  } catch (error) {
    showToast('Erro no Cadastro', error.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

async function handleDeleteProduct(productId, productName) {
  const confirmed = confirm(`Tem certeza que deseja excluir o produto "${productName}"?\n\nIsso removerá o produto permanentemente e apagará qualquer histórico de vendas associado a ele.`);
  if (!confirmed) return;

  try {
    await safeFetch(`${API_BASE}/produtos/${productId}`, {
      method: 'DELETE'
    });

    showToast('Produto Excluído', `"${productName}" foi removido com sucesso!`, 'success');
    await refreshDashboardData();
  } catch (error) {
    showToast('Erro ao Excluir', error.message, 'error');
  }
}

async function handleRestockProduct(productId, productName) {
  const qtyStr = prompt(`Quantas unidades deseja ADICIONAR ao estoque do produto "${productName}"?`);
  if (qtyStr === null) return; // Cancelado pelo usuário

  const qty = parseInt(qtyStr.trim());
  if (isNaN(qty) || qty <= 0) {
    showToast('Quantidade Inválida', 'Por favor, informe um número inteiro maior que zero.', 'warning');
    return;
  }

  try {
    await safeFetch(`${API_BASE}/produtos/${productId}/adicionar-estoque?quantidade=${qty}`, {
      method: 'POST'
    });

    showToast('Estoque Atualizado', `Adicionadas ${qty} un. ao estoque de "${productName}".`, 'success');
    await refreshDashboardData();
  } catch (error) {
    showToast('Erro ao Adicionar', error.message, 'error');
  }
}

// --- VENDAS ---
async function loadSales() {
  try {
    state.sales = await safeFetch(`${API_BASE}/vendas`);
    renderSalesTable();
  } catch (error) {
    showToast('Erro de Vendas', error.message, 'error');
  }
}

function renderSalesTable() {
  const tbody = document.getElementById('sales-table-body');
  if (!tbody) return;

  if (state.sales.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">Nenhuma venda registrada ainda.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.sales.map(sale => {
    const dateObj = new Date(sale.data_venda);
    const dateFormatted = dateObj.toLocaleDateString('pt-BR') + ' ' + dateObj.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const formattedTotal = sale.total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

    return `
      <tr>
        <td class="text-muted font-medium">${dateFormatted}</td>
        <td class="font-semibold">${escapeHTML(sale.produto_nome)}</td>
        <td class="text-center font-bold">${sale.quantidade}</td>
        <td class="text-right font-medium text-wine">${formattedTotal}</td>
      </tr>
    `;
  }).join('');
}

function calculateSaleTotal() {
  const select = document.getElementById('sale-product-select');
  const qtyInput = document.getElementById('sale-quantity');
  const priceDisplay = document.getElementById('sale-unit-price');
  const totalDisplay = document.getElementById('sale-total-value');

  if (!select || !qtyInput || !priceDisplay || !totalDisplay) return;

  const selectedOption = select.options[select.selectedIndex];
  if (!selectedOption || select.value === "") {
    priceDisplay.textContent = 'R$ 0,00';
    totalDisplay.textContent = 'R$ 0,00';
    return;
  }

  const unitPrice = parseFloat(selectedOption.getAttribute('data-price'));
  const stock = parseInt(selectedOption.getAttribute('data-stock'));
  const quantity = parseInt(qtyInput.value) || 0;

  // Limitação de estoque visual
  if (quantity > stock) {
    qtyInput.setCustomValidity(`Quantidade máxima disponível: ${stock}`);
    qtyInput.reportValidity();
  } else {
    qtyInput.setCustomValidity('');
  }

  const total = unitPrice * quantity;

  priceDisplay.textContent = unitPrice.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  totalDisplay.textContent = total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

async function handleCreateSale(event) {
  event.preventDefault();
  const select = document.getElementById('sale-product-select');
  const qtyInput = document.getElementById('sale-quantity');
  const btn = document.getElementById('btn-sale-submit');

  const produto_id = parseInt(select.value);
  const qty = parseInt(qtyInput.value);

  if (!produto_id) {
    showToast('Formulário Incompleto', 'Selecione um produto para realizar a venda.', 'warning');
    return;
  }

  try {
    btn.disabled = true;
    const data = await safeFetch(`${API_BASE}/vendas`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ produto_id, quantidade: qty })
    });

    showToast('Venda Efetuada!', `Registrada venda de ${data.quantidade} un. de "${data.produto_nome}".`, 'success');
    document.getElementById('sale-form').reset();
    await refreshDashboardData();
  } catch (error) {
    showToast('Erro na Venda', error.message, 'error');
  } finally {
    btn.disabled = false;
  }
}

// --- DIALOG MODAL CONTROLLER (NATIVO & COMPATIBILIDADE) ---
const modal = document.getElementById('new-product-dialog');

function openNewProductModal() {
  if (modal) {
    modal.showModal();
  }
}

function closeNewProductModal() {
  if (modal) {
    modal.close();
  }
}

// Fallback de light-dismiss para navegadores antigos
if (modal && !('closedBy' in HTMLDialogElement.prototype)) {
  modal.addEventListener('click', (event) => {
    if (event.target !== modal) return;

    const rect = modal.getBoundingClientRect();
    const isInside = (
      rect.top <= event.clientY &&
      event.clientY <= rect.top + rect.height &&
      rect.left <= event.clientX &&
      event.clientX <= rect.left + rect.width
    );

    if (!isInside) {
      modal.close();
    }
  });
}

// --- AUXILIARES ---
function escapeHTML(str) {
  return str.replace(/[&<>'"]/g,
    tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag)
  );
}

// --- INICIALIZAÇÃO DO APP ---
document.addEventListener('DOMContentLoaded', () => {
  // Alerta especial de segurança caso o app seja aberto via arquivo local (file://)
  if (window.location.protocol === 'file:') {
    showToast(
      'Acesso via Arquivo Local',
      'O app foi aberto diretamente pelo arquivo HTML. Por favor, acesse através do servidor (ex: http://localhost:8080/ ou http://127.0.0.1:8080/) para que as operações do banco funcionem.',
      'warning'
    );
  }

  // Carrega os dados operacionais do painel imediatamente no carregamento
  refreshDashboardData();
});
