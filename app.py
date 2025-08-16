# app.py
# ------------------------------------------------------------
# Clone de um app Base44 ("ProfitFlow") em Python
# Stack: Flask (backend + templates), SQLAlchemy (SQLite), HTMX (interações sem recarregar a página) e Tailwind (estilos via CDN).
# Funcionalidades incluídas:
#  - Dashboard mensal com cartões (Receita, Taxas, Custo, Lucro)
#  - Aba Compras (cadastro de produtos comprados com custo unitário)
#  - Aba Vendas (cadastro de vendas por produto, com preço unitário e quantidade)
#  - Cálculo automático do lucro: lucro = receita - (taxas marketplace + imposto + taxa fixa) - custo
#    * Taxa marketplace (% sobre a venda)
#    * Imposto (% sobre a venda)
#    * Taxa fixa por item (em R$)
#  - Configurações para ajustar as taxas (padrão: 20% marketplace, 8% imposto, R$4,00 fixo)
#  - CRUD inline com HTMX (linhas editáveis e atualização imediata)
#  - Exportação CSV (compras e vendas)
#  - Módulo de "Boletos" simples (do starter) mantido
#
# Observação: o link do Base44 exige JavaScript e não pôde ser carregado aqui. Este clone implementa o fluxo típico
# que você descreveu anteriormente (compras, vendas e cálculo de lucro com 20% + R$4 + 8%). Ao enviar prints/telas
# do seu app, eu ajusto layout e regras 1:1.
# ------------------------------------------------------------

from flask import Flask, render_template, request, redirect, url_for, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from decimal import Decimal
import os
import pathlib

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -----------------------
# Modelos
# -----------------------
class Boleto(db.Model):
    __tablename__ = 'boletos'
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    valor_centavos = db.Column(db.Integer, nullable=False, default=0)
    vencimento = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='aberto')  # aberto | pago | cancelado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Compra(db.Model):
    __tablename__ = 'compras'
    id = db.Column(db.Integer, primary_key=True)
    produto = db.Column(db.String(200), nullable=False)
    custo_unitario_cent = db.Column(db.Integer, nullable=False, default=0)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    data = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Venda(db.Model):
    __tablename__ = 'vendas'
    id = db.Column(db.Integer, primary_key=True)
    produto = db.Column(db.String(200), nullable=False)
    preco_unitario_cent = db.Column(db.Integer, nullable=False, default=0)
    quantidade = db.Column(db.Integer, nullable=False, default=1)
    data = db.Column(db.Date, nullable=False, default=date.today)
    # custo_unitario_override permite ajustar o custo usado no cálculo, se necessário
    custo_unitario_override_cent = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Config(db.Model):
    __tablename__ = 'config'
    id = db.Column(db.Integer, primary_key=True)
    marketplace_percent = db.Column(db.Float, nullable=False, default=20.0)  # 20%
    imposto_percent = db.Column(db.Float, nullable=False, default=8.0)        # 8%
    taxa_fixa_cent = db.Column(db.Integer, nullable=False, default=400)       # R$ 4,00

# -----------------------
# Templates embutidos (para rodar em 1 arquivo)
# -----------------------
TEMPLATES = {
'base.html': r'''<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title or 'ProfitFlow' }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  <link rel="icon" href="data:,">
  <style>
    .badge { @apply px-2 py-0.5 rounded-full text-xs font-medium; }
    .navlink { @apply px-3 py-2 rounded-xl text-sm; }
    .navlink-active { @apply bg-gray-900 text-white; }
    .card { @apply bg-white rounded-2xl shadow p-4; }
  </style>
</head>
<body class="bg-gray-50 min-h-screen">
  <header class="bg-white border-b">
    <div class="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
      <a href="{{ url_for('dashboard') }}" class="text-lg font-semibold">ProfitFlow</a>
      <nav class="flex gap-2">
        {% set here = request.path %}
        <a href="{{ url_for('dashboard') }}" class="navlink {{ 'navlink-active' if here.startswith('/dashboard') or here=='/' else '' }}">Dashboard</a>
        <a href="{{ url_for('compras') }}" class="navlink {{ 'navlink-active' if here.startswith('/compras') else '' }}">Compras</a>
        <a href="{{ url_for('vendas') }}" class="navlink {{ 'navlink-active' if here.startswith('/vendas') else '' }}">Vendas</a>
        <a href="{{ url_for('index') }}" class="navlink {{ 'navlink-active' if here.startswith('/boletos') else '' }}">Boletos</a>
        <a href="{{ url_for('configuracoes') }}" class="navlink {{ 'navlink-active' if here.startswith('/config') else '' }}">Config</a>
      </nav>
      <form method="get" action="{{ request.path }}" class="hidden md:flex gap-2">
        {% if request.endpoint in ['vendas', 'compras'] %}
        <input type="month" name="m" value="{{ m or '' }}" class="border rounded-lg px-3 py-2">
        <button class="px-4 py-2 bg-gray-900 text-white rounded-xl">Filtrar</button>
        {% endif %}
      </form>
    </div>
  </header>
  <main class="max-w-6xl mx-auto p-4">
    {% block content %}{% endblock %}
  </main>
  <footer class="max-w-6xl mx-auto p-4 text-center text-sm text-gray-500">
    Flask + HTMX • Ajustaremos o layout para ficar idêntico ao seu Base44
  </footer>
</body>
</html>''',

'dashboard.html': r'''{% extends 'base.html' %}
{% block content %}
  <h1 class="text-xl font-semibold mb-4">Resumo — {{ mes_label }}</h1>
  <div class="grid md:grid-cols-4 gap-4 mb-6">
    <div class="card"><div class="text-gray-500 text-sm">Receita Bruta</div><div class="text-2xl font-semibold">{{ tot_receita | moeda }}</div></div>
    <div class="card"><div class="text-gray-500 text-sm">Taxas (Mk + Imp + Fixo)</div><div class="text-2xl font-semibold">{{ tot_taxas | moeda }}</div></div>
    <div class="card"><div class="text-gray-500 text-sm">Custo</div><div class="text-2xl font-semibold">{{ tot_custo | moeda }}</div></div>
    <div class="card"><div class="text-gray-500 text-sm">Lucro</div><div class="text-2xl font-semibold">{{ tot_lucro | moeda }}</div></div>
  </div>

  <div class="card">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-lg font-semibold">Vendas do mês</h2>
      <a href="{{ url_for('export_vendas_csv') }}" class="text-sm text-blue-600 hover:underline">Exportar CSV</a>
    </div>
    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-gray-500 border-b">
          <th class="py-2 pr-2">Data</th>
          <th class="py-2 pr-2">Produto</th>
          <th class="py-2 pr-2">Qtd</th>
          <th class="py-2 pr-2">Preço</th>
          <th class="py-2 pr-2">Receita</th>
          <th class="py-2 pr-2">Custo</th>
          <th class="py-2 pr-2">Taxas</th>
          <th class="py-2 pr-2">Lucro</th>
        </tr></thead>
        <tbody>
          {% for r in linhas %}
          <tr class="border-b last:border-0">
            <td class="py-3 pr-2">{{ r.venda.data.strftime('%d/%m/%Y') }}</td>
            <td class="py-3 pr-2">{{ r.venda.produto }}</td>
            <td class="py-3 pr-2">{{ r.venda.quantidade }}</td>
            <td class="py-3 pr-2">{{ r.preco_unitario | moeda }}</td>
            <td class="py-3 pr-2">{{ r.receita | moeda }}</td>
            <td class="py-3 pr-2">{{ r.custo | moeda }}</td>
            <td class="py-3 pr-2">{{ r.taxas | moeda }}</td>
            <td class="py-3 pr-2 font-semibold {{ 'text-emerald-700' if r.lucro>=0 else 'text-red-600' }}">{{ r.lucro | moeda }}</td>
          </tr>
          {% else %}
          <tr><td colspan="8" class="py-6 text-center text-gray-400">Sem vendas neste mês</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
{% endblock %}''',

'compras.html': r'''{% extends 'base.html' %}
{% block content %}
<div class="grid md:grid-cols-3 gap-6">
  <section class="md:col-span-1 card">
    <h2 class="text-lg font-semibold mb-3">Nova compra</h2>
    <form hx-post="{{ url_for('create_compra') }}" hx-target="#compras-body" hx-swap="afterbegin" class="space-y-3">
      <div><label class="block text-sm mb-1">Produto</label>
        <input required name="produto" class="w-full border rounded-lg px-3 py-2" placeholder="Ex.: Chaleira elétrica">
      </div>
      <div><label class="block text-sm mb-1">Custo unitário</label>
        <input required name="custo" class="w-full border rounded-lg px-3 py-2" placeholder="Ex.: 35,90">
      </div>
      <div><label class="block text-sm mb-1">Quantidade</label>
        <input type="number" min="1" name="quantidade" value="1" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div><label class="block text-sm mb-1">Data</label>
        <input type="date" name="data" value="{{ today_iso }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <button class="w-full py-2 bg-emerald-600 text-white rounded-xl">Adicionar</button>
    </form>
  </section>

  <section class="md:col-span-2 card">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-lg font-semibold">Compras</h2>
      <a href="{{ url_for('export_compras_csv') }}" class="text-sm text-blue-600 hover:underline">Exportar CSV</a>
    </div>
    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-gray-500 border-b">
          <th class="py-2 pr-2">Produto</th>
          <th class="py-2 pr-2">Custo unit.</th>
          <th class="py-2 pr-2">Qtd</th>
          <th class="py-2 pr-2">Data</th>
          <th class="py-2 pr-2">Ações</th>
        </tr></thead>
        <tbody id="compras-body">
          {% for c in compras %}
            {% include '_compra_row.html' %}
          {% else %}
          <tr><td colspan="5" class="py-6 text-center text-gray-400">Sem compras</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </section>
</div>
{% endblock %}''',

'_compra_row.html': r'''<tr id="compra-{{ c.id }}" class="border-b last:border-0">
  <td class="py-3 pr-2">{{ c.produto }}</td>
  <td class="py-3 pr-2">{{ c.custo_unitario_cent | moeda }}</td>
  <td class="py-3 pr-2">{{ c.quantidade }}</td>
  <td class="py-3 pr-2">{{ c.data.strftime('%d/%m/%Y') }}</td>
  <td class="py-3 pr-2 flex gap-2">
    <button hx-get="{{ url_for('edit_compra', id=c.id) }}" hx-target="#compra-{{ c.id }}" hx-swap="outerHTML" class="px-3 py-1 rounded-lg border">Editar</button>
    <button hx-delete="{{ url_for('delete_compra', id=c.id) }}" hx-target="#compra-{{ c.id }}" hx-swap="outerHTML:remove" class="px-3 py-1 rounded-lg border text-red-600">Excluir</button>
  </td>
</tr>''',

'_compra_edit_row.html': r'''<tr id="compra-{{ c.id }}" class="border-b last:border-0 bg-amber-50">
  <td class="py-3 pr-2" colspan="5">
    <form hx-post="{{ url_for('update_compra', id=c.id) }}" hx-target="#compra-{{ c.id }}" hx-swap="outerHTML" class="grid md:grid-cols-5 gap-3 items-end">
      <div class="md:col-span-2">
        <label class="block text-xs mb-1">Produto</label>
        <input name="produto" value="{{ c.produto }}" class="w-full border rounded-lg px-3 py-2" required>
      </div>
      <div>
        <label class="block text-xs mb-1">Custo unitário</label>
        <input name="custo" value="{{ (c.custo_unitario_cent/100)|format_valor }}" class="w-full border rounded-lg px-3 py-2" required>
      </div>
      <div>
        <label class="block text-xs mb-1">Quantidade</label>
        <input type="number" name="quantidade" min="1" value="{{ c.quantidade }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div>
        <label class="block text-xs mb-1">Data</label>
        <input type="date" name="data" value="{{ c.data.strftime('%Y-%m-%d') }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div class="flex gap-2">
        <button class="px-4 py-2 bg-emerald-600 text-white rounded-xl">Salvar</button>
        <button type="button" hx-get="{{ url_for('compra_row', id=c.id) }}" hx-target="#compra-{{ c.id }}" hx-swap="outerHTML" class="px-4 py-2 bg-gray-200 rounded-xl">Cancelar</button>
      </div>
    </form>
  </td>
</tr>''',

'vendas.html': r'''{% extends 'base.html' %}
{% block content %}
<div class="grid md:grid-cols-3 gap-6">
  <section class="md:col-span-1 card">
    <h2 class="text-lg font-semibold mb-3">Nova venda</h2>
    <form hx-post="{{ url_for('create_venda') }}" hx-target="#vendas-body" hx-swap="afterbegin" class="space-y-3">
      <div><label class="block text-sm mb-1">Produto</label>
        <input required name="produto" class="w-full border rounded-lg px-3 py-2" placeholder="Ex.: Chaleira elétrica">
      </div>
      <div><label class="block text-sm mb-1">Preço unitário</label>
        <input required name="preco" class="w-full border rounded-lg px-3 py-2" placeholder="Ex.: 99,90">
      </div>
      <div><label class="block text-sm mb-1">Quantidade</label>
        <input type="number" min="1" name="quantidade" value="1" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div><label class="block text-sm mb-1">Data</label>
        <input type="date" name="data" value="{{ today_iso }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div><label class="block text-sm mb-1">Custo unitário (opcional)</label>
        <input name="custo" class="w-full border rounded-lg px-3 py-2" placeholder="se vazio, usa última compra">
      </div>
      <button class="w-full py-2 bg-emerald-600 text-white rounded-xl">Adicionar</button>
    </form>
  </section>

  <section class="md:col-span-2 card">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-lg font-semibold">Vendas</h2>
      <a href="{{ url_for('export_vendas_csv') }}" class="text-sm text-blue-600 hover:underline">Exportar CSV</a>
    </div>
    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead><tr class="text-left text-gray-500 border-b">
          <th class="py-2 pr-2">Produto</th>
          <th class="py-2 pr-2">Preço unit.</th>
          <th class="py-2 pr-2">Qtd</th>
          <th class="py-2 pr-2">Data</th>
          <th class="py-2 pr-2">Custo usado</th>
          <th class="py-2 pr-2">Lucro (calc)</th>
          <th class="py-2 pr-2">Ações</th>
        </tr></thead>
        <tbody id="vendas-body">
          {% for v in vendas %}
            {% include '_venda_row.html' %}
          {% else %}
          <tr><td colspan="7" class="py-6 text-center text-gray-400">Sem vendas</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </section>
</div>
{% endblock %}''',

'_venda_row.html': r'''<tr id="venda-{{ v.id }}" class="border-b last:border-0">
  <td class="py-3 pr-2">{{ v.produto }}</td>
  <td class="py-3 pr-2">{{ v.preco_unitario_cent | moeda }}</td>
  <td class="py-3 pr-2">{{ v.quantidade }}</td>
  <td class="py-3 pr-2">{{ v.data.strftime('%d/%m/%Y') }}</td>
  {% set custo = custo_para_venda(v) %}
  <td class="py-3 pr-2">{{ custo | moeda }}</td>
  {% set receita = v.preco_unitario_cent * v.quantidade %}
  {% set taxas = calc_taxas(receita) + (config.taxa_fixa_cent * v.quantidade) %}
  {% set lucro = receita - taxas - (custo * v.quantidade) %}
  <td class="py-3 pr-2 font-semibold {{ 'text-emerald-700' if lucro>=0 else 'text-red-600' }}">{{ lucro | moeda }}</td>
  <td class="py-3 pr-2 flex gap-2">
    <button hx-get="{{ url_for('edit_venda', id=v.id) }}" hx-target="#venda-{{ v.id }}" hx-swap="outerHTML" class="px-3 py-1 rounded-lg border">Editar</button>
    <button hx-delete="{{ url_for('delete_venda', id=v.id) }}" hx-target="#venda-{{ v.id }}" hx-swap="outerHTML:remove" class="px-3 py-1 rounded-lg border text-red-600">Excluir</button>
  </td>
</tr>''',

'_venda_edit_row.html': r'''<tr id="venda-{{ v.id }}" class="border-b last:border-0 bg-amber-50">
  <td class="py-3 pr-2" colspan="7">
    <form hx-post="{{ url_for('update_venda', id=v.id) }}" hx-target="#venda-{{ v.id }}" hx-swap="outerHTML" class="grid md:grid-cols-6 gap-3 items-end">
      <div class="md:col-span-2">
        <label class="block text-xs mb-1">Produto</label>
        <input name="produto" value="{{ v.produto }}" class="w-full border rounded-lg px-3 py-2" required>
      </div>
      <div>
        <label class="block text-xs mb-1">Preço unitário</label>
        <input name="preco" value="{{ (v.preco_unitario_cent/100)|format_valor }}" class="w-full border rounded-lg px-3 py-2" required>
      </div>
      <div>
        <label class="block text-xs mb-1">Quantidade</label>
        <input type="number" min="1" name="quantidade" value="{{ v.quantidade }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div>
        <label class="block text-xs mb-1">Data</label>
        <input type="date" name="data" value="{{ v.data.strftime('%Y-%m-%m') }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div>
        <label class="block text-xs mb-1">Custo unitário (override)</label>
        <input name="custo" value="{{ ( (v.custo_unitario_override_cent or 0)/100 )|format_valor }}" class="w-full border rounded-lg px-3 py-2" placeholder="opcional">
      </div>
      <div class="flex gap-2">
        <button class="px-4 py-2 bg-emerald-600 text-white rounded-xl">Salvar</button>
        <button type="button" hx-get="{{ url_for('venda_row', id=v.id) }}" hx-target="#venda-{{ v.id }}" hx-swap="outerHTML" class="px-4 py-2 bg-gray-200 rounded-xl">Cancelar</button>
      </div>
    </form>
  </td>
</tr>''',

'boletos.html': r'''{% extends 'base.html' %}
{% block content %}
<div class="grid md:grid-cols-3 gap-6">
  <section class="md:col-span-1 card">
    <h2 class="text-lg font-semibold mb-3">Novo boleto</h2>
    <form hx-post="{{ url_for('create_boleto') }}" hx-target="#table-body" hx-swap="afterbegin" class="space-y-3">
      <div>
        <label class="block text-sm mb-1">Descrição</label>
        <input required name="descricao" class="w-full border rounded-lg px-3 py-2" placeholder="Ex.: Conta de luz">
      </div>
      <div>
        <label class="block text-sm mb-1">Valor</label>
        <input required name="valor" class="w-full border rounded-lg px-3 py-2" placeholder="Ex.: 123,45">
      </div>
      <div>
        <label class="block text-sm mb-1">Vencimento</label>
        <input type="date" name="vencimento" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div>
        <label class="block text-sm mb-1">Status</label>
        <select name="status" class="w-full border rounded-lg px-3 py-2">
          <option value="aberto">Aberto</option>
          <option value="pago">Pago</option>
          <option value="cancelado">Cancelado</option>
        </select>
      </div>
      <button class="w-full py-2 bg-emerald-600 text-white rounded-xl">Adicionar</button>
    </form>
  </section>
  <section class="md:col-span-2 card">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-lg font-semibold">Boletos</h2>
      <a href="{{ url_for('export_boletos_csv') }}" class="text-sm text-blue-600 hover:underline">Exportar CSV</a>
    </div>
    <div class="overflow-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-gray-500 border-b">
            <th class="py-2 pr-2">Descrição</th>
            <th class="py-2 pr-2">Valor</th>
            <th class="py-2 pr-2">Vencimento</th>
            <th class="py-2 pr-2">Status</th>
            <th class="py-2 pr-2">Ações</th>
          </tr>
        </thead>
        <tbody id="table-body">
          {% for b in boletos %}
            {% include '_boleto_row.html' %}
          {% else %}
          <tr>
            <td colspan="5" class="py-6 text-center text-gray-400">Sem boletos ainda</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </section>
</div>
{% endblock %}''',

'_boleto_row.html': r'''<tr id="row-{{ b.id }}" class="border-b last:border-0">
  <td class="py-3 pr-2">{{ b.descricao }}</td>
  <td class="py-3 pr-2">{{ b.valor_centavos | moeda }}</td>
  <td class="py-3 pr-2">{{ b.vencimento.strftime('%d/%m/%Y') if b.vencimento else '-' }}</td>
  <td class="py-3 pr-2">
    {% set color = 'bg-yellow-100 text-yellow-800' if b.status=='aberto' else ('bg-green-100 text-green-800' if b.status=='pago' else 'bg-gray-200 text-gray-700') %}
    <span class="badge {{ color }}">{{ b.status|capitalize }}</span>
  </td>
  <td class="py-3 pr-2 whitespace-nowrap flex gap-2">
    <button hx-post="{{ url_for('toggle_status', id=b.id) }}" hx-target="#row-{{ b.id }}" hx-swap="outerHTML" class="px-3 py-1 rounded-lg border">Alternar</button>
    <button hx-get="{{ url_for('edit_boleto', id=b.id) }}" hx-target="#row-{{ b.id }}" hx-swap="outerHTML" class="px-3 py-1 rounded-lg border">Editar</button>
    <button hx-delete="{{ url_for('delete_boleto', id=b.id) }}" hx-target="#row-{{ b.id }}" hx-swap="outerHTML:remove" class="px-3 py-1 rounded-lg border text-red-600">Excluir</button>
  </td>
</tr>''',

'_boleto_edit_row.html': r'''<tr id="row-{{ b.id }}" class="border-b last:border-0 bg-amber-50">
  <td class="py-3 pr-2" colspan="5">
    <form hx-post="{{ url_for('update_boleto', id=b.id) }}" hx-target="#row-{{ b.id }}" hx-swap="outerHTML" class="grid md:grid-cols-5 gap-3 items-end">
      <div class="md:col-span-2">
        <label class="block text-xs mb-1">Descrição</label>
        <input name="descricao" value="{{ b.descricao }}" class="w-full border rounded-lg px-3 py-2" required>
      </div>
      <div>
        <label class="block text-xs mb-1">Valor</label>
        <input name="valor" value="{{ (b.valor_centavos/100)|format_valor }}" class="w-full border rounded-lg px-3 py-2" required>
      </div>
      <div>
        <label class="block text-xs mb-1">Vencimento</label>
        <input type="date" name="vencimento" value="{{ b.vencimento.strftime('%Y-%m-%d') if b.vencimento else '' }}" class="w-full border rounded-lg px-3 py-2">
      </div>
      <div>
        <label class="block text-xs mb-1">Status</label>
        <select name="status" class="w-full border rounded-lg px-3 py-2">
          <option value="aberto" {% if b.status=='aberto' %}selected{% endif %}>Aberto</option>
          <option value="pago" {% if b.status=='pago' %}selected{% endif %}>Pago</option>
          <option value="cancelado" {% if b.status=='cancelado' %}selected{% endif %}>Cancelado</option>
        </select>
      </div>
      <div class="flex gap-2">
        <button class="px-4 py-2 bg-emerald-600 text-white rounded-xl">Salvar</button>
        <button type="button" hx-get="{{ url_for('boleto_row', id=b.id) }}" hx-target="#row-{{ b.id }}" hx-swap="outerHTML" class="px-4 py-2 bg-gray-200 rounded-xl">Cancelar</button>
      </div>
    </form>
  </td>
</tr>''',

'config.html': r'''{% extends 'base.html' %}
{% block content %}
<div class="max-w-xl card mx-auto">
  <h2 class="text-lg font-semibold mb-3">Configurações</h2>
  <form method="post" class="grid gap-3">
    <div>
      <label class="block text-sm mb-1">Taxa marketplace (%)</label>
      <input name="marketplace" value="{{ config.marketplace_percent }}" class="w-full border rounded-lg px-3 py-2" required>
    </div>
    <div>
      <label class="block text-sm mb-1">Imposto (%)</label>
      <input name="imposto" value="{{ config.imposto_percent }}" class="w-full border rounded-lg px-3 py-2" required>
    </div>
    <div>
      <label class="block text-sm mb-1">Taxa fixa por item (R$)</label>
      <input name="fixo" value="{{ (config.taxa_fixa_cent/100)|format_valor }}" class="w-full border rounded-lg px-3 py-2" required>
    </div>
    <button class="py-2 bg-emerald-600 text-white rounded-xl">Salvar</button>
  </form>
</div>
{% endblock %}'''
}

# -----------------------
# Utilitários
# -----------------------

def ensure_templates():
    base = pathlib.Path('templates')
    base.mkdir(parents=True, exist_ok=True)
    for name, content in TEMPLATES.items():
        path = base / name
        if not path.exists():
            path.write_text(content, encoding='utf-8')

@app.template_filter('moeda')
def moeda(centavos: int) -> str:
    sign = '-' if centavos < 0 else ''
    reais = abs(centavos) // 100
    c = abs(centavos) % 100
    return f"{sign}R$ {reais:,},{c:02d}".replace(',', 'X').replace('.', ',').replace('X', '.')

@app.template_filter('format_valor')
def format_valor(v: float) -> str:
    return f"{v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def parse_valor_to_centavos(s: str) -> int:
    s = (s or '').strip()
    s = s.replace('R$', '').replace(' ', '')
    if s.count(',') == 1 and s.count('.') >= 1:
        s = s.replace('.', '').replace(',', '.')
    else:
        s = s.replace(',', '.')
    try:
        dec = Decimal(s)
    except Exception:
        dec = Decimal('0')
    return int(dec * 100)


def parse_percent(s: str) -> float:
    s = (s or '').strip().replace('%', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0


def month_bounds(ym: str):
    # ym: 'YYYY-MM'
    if not ym:
        today = date.today()
        ym = f"{today.year}-{today.month:02d}"
    y, m = map(int, ym.split('-'))
    start = date(y, m, 1)
    if m == 12:
        end = date(y+1, 1, 1)
    else:
        end = date(y, m+1, 1)
    return start, end


def latest_compra_custo(produto: str) -> int:
    c = (
        Compra.query
        .filter(Compra.produto.ilike(produto))
        .order_by(Compra.data.desc(), Compra.created_at.desc())
        .first()
    )
    return c.custo_unitario_cent if c else 0

# Funções de cálculo (usadas nos templates via contexto)

def _get_config() -> Config:
    cfg = Config.query.get(1)
    if not cfg:
        cfg = Config(id=1)
        db.session.add(cfg)
        db.session.commit()
    return cfg


def calc_taxas(receita_cent: int) -> int:
    cfg = _get_config()
    mk = int(round(receita_cent * (cfg.marketplace_percent / 100.0)))
    imp = int(round(receita_cent * (cfg.imposto_percent / 100.0)))
    return mk + imp


def custo_para_venda(venda: Venda) -> int:
    if venda.custo_unitario_override_cent is not None:
        return venda.custo_unitario_override_cent
    return latest_compra_custo(venda.produto)

# -----------------------
# Rotas principais
# -----------------------
@app.before_first_request
def init():
    ensure_templates()
    db.create_all()
    _get_config()

@app.route('/')
def home_redirect():
    return redirect(url_for('dashboard'))

@app.get('/dashboard')
def dashboard():
    today = date.today()
    ym = request.args.get('m') or f"{today.year}-{today.month:02d}"
    start, end = month_bounds(ym)
    vendas = (Venda.query.filter(Venda.data >= start, Venda.data < end)
              .order_by(Venda.data.desc(), Venda.created_at.desc()).all())
    cfg = _get_config()
    linhas = []
    tot_receita = tot_taxas = tot_custo = tot_lucro = 0
    for v in vendas:
        receita = v.preco_unitario_cent * v.quantidade
        custo_u = custo_para_venda(v)
        custo = custo_u * v.quantidade
        taxas = calc_taxas(receita) + (cfg.taxa_fixa_cent * v.quantidade)
        lucro = receita - taxas - custo
        tot_receita += receita
        tot_taxas += taxas
        tot_custo += custo
        tot_lucro += lucro
        linhas.append({
            'venda': v,
            'preco_unitario': v.preco_unitario_cent,
            'receita': receita,
            'custo': custo_u,
            'taxas': taxas,
            'lucro': lucro,
        })
    mes_label = start.strftime('%m/%Y')
    return render_template('dashboard.html', title='Dashboard', linhas=linhas,
                           tot_receita=tot_receita, tot_taxas=tot_taxas,
                           tot_custo=tot_custo, tot_lucro=tot_lucro,
                           mes_label=mes_label)

# -----------------------
# Compras (CRUD)
# -----------------------
@app.get('/compras')
def compras():
    compras = Compra.query.order_by(Compra.data.desc(), Compra.created_at.desc()).all()
    return render_template('compras.html', title='Compras', compras=compras, today_iso=date.today().isoformat())

@app.post('/compras')
def create_compra():
    prod = (request.form.get('produto') or '').strip()
    custo = request.form.get('custo') or '0'
    qtd = int(request.form.get('quantidade') or 1)
    d = request.form.get('data') or date.today().isoformat()
    if not prod:
        abort(400, 'Produto é obrigatório')
    c_cent = parse_valor_to_centavos(custo)
    try:
        data = datetime.strptime(d, '%Y-%m-%d').date()
    except ValueError:
        data = date.today()
    c = Compra(produto=prod, custo_unitario_cent=c_cent, quantidade=qtd, data=data)
    db.session.add(c)
    db.session.commit()
    if request.headers.get('HX-Request'):
        return render_template('_compra_row.html', c=c)
    return redirect(url_for('compras'))

@app.get('/compras/<int:id>/row')
def compra_row(id: int):
    c = Compra.query.get_or_404(id)
    return render_template('_compra_row.html', c=c)

@app.get('/compras/<int:id>/edit')
def edit_compra(id: int):
    c = Compra.query.get_or_404(id)
    return render_template('_compra_edit_row.html', c=c)

@app.post('/compras/<int:id>/update')
def update_compra(id: int):
    c = Compra.query.get_or_404(id)
    c.produto = (request.form.get('produto') or '').strip()
    c.custo_unitario_cent = parse_valor_to_centavos(request.form.get('custo') or '0')
    c.quantidade = int(request.form.get('quantidade') or 1)
    d = request.form.get('data') or ''
    if d:
        try:
            c.data = datetime.strptime(d, '%Y-%m-%d').date()
        except ValueError:
            pass
    db.session.commit()
    return render_template('_compra_row.html', c=c)

@app.route('/compras/<int:id>', methods=['DELETE'])
def delete_compra(id: int):
    c = Compra.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return ('', 204)

# -----------------------
# Vendas (CRUD)
# -----------------------
@app.get('/vendas')
def vendas():
    vendas = Venda.query.order_by(Venda.data.desc(), Venda.created_at.desc()).all()
    return render_template('vendas.html', title='Vendas', vendas=vendas, today_iso=date.today().isoformat(), config=_get_config())

@app.post('/vendas')
def create_venda():
    prod = (request.form.get('produto') or '').strip()
    preco = request.form.get('preco') or '0'
    qtd = int(request.form.get('quantidade') or 1)
    d = request.form.get('data') or date.today().isoformat()
    custo = request.form.get('custo') or ''
    if not prod:
        abort(400, 'Produto é obrigatório')
    preco_cent = parse_valor_to_centavos(preco)
    custo_cent = parse_valor_to_centavos(custo) if custo else None
    try:
        data = datetime.strptime(d, '%Y-%m-%d').date()
    except ValueError:
        data = date.today()
    v = Venda(produto=prod, preco_unitario_cent=preco_cent, quantidade=qtd, data=data,
              custo_unitario_override_cent=custo_cent)
    db.session.add(v)
    db.session.commit()
    if request.headers.get('HX-Request'):
        return render_template('_venda_row.html', v=v, config=_get_config(), calc_taxas=calc_taxas, custo_para_venda=custo_para_venda)
    return redirect(url_for('vendas'))

@app.get('/vendas/<int:id>/row')
def venda_row(id: int):
    v = Venda.query.get_or_404(id)
    return render_template('_venda_row.html', v=v, config=_get_config(), calc_taxas=calc_taxas, custo_para_venda=custo_para_venda)

@app.get('/vendas/<int:id>/edit')
def edit_venda(id: int):
    v = Venda.query.get_or_404(id)
    return render_template('_venda_edit_row.html', v=v)

@app.post('/vendas/<int:id>/update')
def update_venda(id: int):
    v = Venda.query.get_or_404(id)
    v.produto = (request.form.get('produto') or '').strip()
    v.preco_unitario_cent = parse_valor_to_centavos(request.form.get('preco') or '0')
    v.quantidade = int(request.form.get('quantidade') or 1)
    d = request.form.get('data') or ''
    custo = request.form.get('custo') or ''
    v.custo_unitario_override_cent = parse_valor_to_centavos(custo) if custo else None
    if d:
        try:
            v.data = datetime.strptime(d, '%Y-%m-%d').date()
        except ValueError:
            pass
    db.session.commit()
    return render_template('_venda_row.html', v=v, config=_get_config(), calc_taxas=calc_taxas, custo_para_venda=custo_para_venda)

@app.route('/vendas/<int:id>', methods=['DELETE'])
def delete_venda(id: int):
    v = Venda.query.get_or_404(id)
    db.session.delete(v)
    db.session.commit()
    return ('', 204)

# -----------------------
# Boletos (do starter)
# -----------------------
@app.get('/boletos')
@app.get('/index')
@app.get('/list')
@app.get('/b')
@app.get('/boletos/')
@app.get('/index/')
@app.get('/list/')
@app.get('/b/')
@app.get('/boletos/index')
@app.get('/boletos/list')
@app.get('/boletos/b')
def index():
    boletos = Boleto.query.order_by(Boleto.created_at.desc()).all()
    return render_template('boletos.html', title='Boletos', boletos=boletos)

@app.post('/boletos')
def create_boleto():
    desc = (request.form.get('descricao') or '').strip()
    valor = request.form.get('valor') or '0'
    venc = request.form.get('vencimento') or ''
    status = (request.form.get('status') or 'aberto').strip()
    if not desc:
        abort(400, 'Descrição é obrigatória')
    cent = parse_valor_to_centavos(valor)
    venc_date = None
    if venc:
        try:
            venc_date = datetime.strptime(venc, '%Y-%m-%d').date()
        except ValueError:
            venc_date = None
    b = Boleto(descricao=desc, valor_centavos=cent, vencimento=venc_date, status=status)
    db.session.add(b)
    db.session.commit()
    if request.headers.get('HX-Request'):
        return render_template('_boleto_row.html', b=b)
    return redirect(url_for('index'))

@app.get('/boletos/<int:id>/row')
def boleto_row(id: int):
    b = Boleto.query.get_or_404(id)
    return render_template('_boleto_row.html', b=b)

@app.get('/boletos/<int:id>/edit')
def edit_boleto(id: int):
    b = Boleto.query.get_or_404(id)
    return render_template('_boleto_edit_row.html', b=b)

@app.post('/boletos/<int:id>/update')
def update_boleto(id: int):
    b = Boleto.query.get_or_404(id)
    desc = (request.form.get('descricao') or '').strip()
    valor = request.form.get('valor') or '0'
    venc = request.form.get('vencimento') or ''
    status = (request.form.get('status') or 'aberto').strip()
    if not desc:
        abort(400, 'Descrição é obrigatória')
    b.descricao = desc
    b.valor_centavos = parse_valor_to_centavos(valor)
    if venc:
        try:
            b.vencimento = datetime.strptime(venc, '%Y-%m-%d').date()
        except ValueError:
            b.vencimento = None
    else:
        b.vencimento = None
    b.status = status
    db.session.commit()
    return render_template('_boleto_row.html', b=b)

@app.post('/boletos/<int:id>/toggle')
def toggle_status(id: int):
    b = Boleto.query.get_or_404(id)
    if b.status == 'aberto':
        b.status = 'pago'
    elif b.status == 'pago':
        b.status = 'aberto'
    else:
        b.status = 'aberto'
    db.session.commit()
    return render_template('_boleto_row.html', b=b)

@app.route('/boletos/<int:id>', methods=['DELETE'])
def delete_boleto(id: int):
    b = Boleto.query.get_or_404(id)
    db.session.delete(b)
    db.session.commit()
    return ('', 204)

# -----------------------
# Configurações
# -----------------------
@app.get('/config')
def configuracoes():
    return render_template('config.html', title='Configurações', config=_get_config())

@app.post('/config')
def save_config():
    cfg = _get_config()
    cfg.marketplace_percent = parse_percent(request.form.get('marketplace'))
    cfg.imposto_percent = parse_percent(request.form.get('imposto'))
    cfg.taxa_fixa_cent = parse_valor_to_centavos(request.form.get('fixo') or '0')
    db.session.commit()
    return redirect(url_for('configuracoes'))

# -----------------------
# Exportações CSV
# -----------------------
@app.get('/export/boletos.csv')
def export_boletos_csv():
    boletos = Boleto.query.order_by(Boleto.created_at.desc()).all()
    lines = ['id,descricao,valor_centavos,vencimento,status,created_at']
    for b in boletos:
        venc = b.vencimento.isoformat() if b.vencimento else ''
        row = [str(b.id), b.descricao.replace(',', ' '), str(b.valor_centavos), venc, b.status, b.created_at.isoformat()]
        lines.append(','.join(row))
    return _csv_response('\n'.join(lines), 'boletos.csv')

@app.get('/export/compras.csv')
def export_compras_csv():
    compras = Compra.query.order_by(Compra.data.desc(), Compra.created_at.desc()).all()
    lines = ['id,produto,custo_unitario_cent,quantidade,data,created_at']
    for c in compras:
        row = [str(c.id), c.produto.replace(',', ' '), str(c.custo_unitario_cent), str(c.quantidade), c.data.isoformat(), c.created_at.isoformat()]
        lines.append(','.join(row))
    return _csv_response('\n'.join(lines), 'compras.csv')

@app.get('/export/vendas.csv')
def export_vendas_csv():
    vendas = Venda.query.order_by(Venda.data.desc(), Venda.created_at.desc()).all()
    lines = ['id,produto,preco_unitario_cent,quantidade,data,custo_unitario_override_cent,created_at']
    for v in vendas:
        row = [str(v.id), v.produto.replace(',', ' '), str(v.preco_unitario_cent), str(v.quantidade), v.data.isoformat(), str(v.custo_unitario_override_cent or ''), v.created_at.isoformat()]
        lines.append(','.join(row))
    return _csv_response('\n'.join(lines), 'vendas.csv')


def _csv_response(csv_data: str, filename: str):
    resp = make_response(csv_data)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return resp

# -----------------------
# App
# -----------------------
if __name__ == '__main__':
    ensure_templates()
    with app.app_context():
        db.create_all()
        _get_config()
    app.run(host='127.0.0.1', port=5000, debug=True)
