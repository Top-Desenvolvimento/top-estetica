"""
Top Estética Bucal — Scraper PIX Doutores
Roda via GitHub Actions a cada hora automaticamente.
"""
import asyncio
import json
import os
import datetime
import calendar
import re
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

USUARIO = os.environ.get("SISTEMA_USER", "MANUS")
SENHA   = os.environ.get("SISTEMA_PASS", "MANUS2026")

CIDADES = [
    {"nome": "CAXIAS",      "url": "http://caxias.topesteticabucal.com.br/sistema"},
    {"nome": "FARROUPILHA", "url": "http://farroupilha.topesteticabucal.com.br/sistema"},
    {"nome": "SOLEDADE",    "url": "http://soledade.topesteticabucal.com.br/sistema"},
    {"nome": "ENCANTADO",   "url": "https://encantado.topesteticabucal.com.br/sistema"},
    {"nome": "GARIBALDI",   "url": "http://garibaldi.topesteticabucal.com.br/sistema"},
    {"nome": "VERANOPOLIS", "url": "http://veranopolis.topesteticabucal.com.br/sistema"},
    {"nome": "SS DO CAI",   "url": "https://ssdocai.topesteticabucal.com.br/sistema"},
    {"nome": "BENTO",       "url": "http://bento.topesteticabucal.com.br/sistema"},
    {"nome": "FLORES",      "url": "https://flores.topesteticabucal.com.br/sistema"},
]

def get_periodo():
    hoje = datetime.date.today()
    ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]  # correto para qualquer mês
    primeiro = f"01/{hoje.month:02d}/{hoje.year}"
    ultimo   = f"{ultimo_dia}/{hoje.month:02d}/{hoje.year}"
    mes_ref  = f"{hoje.month:02d}/{hoje.year}"
    return primeiro, ultimo, mes_ref

def parse_valor(texto):
    if not texto:
        return 0.0
    # Remove tudo exceto dígitos, vírgula e ponto
    limpo = re.sub(r'[^\d,\.]', '', texto)
    # Formato brasileiro: 1.234,56
    if ',' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    try:
        return float(limpo)
    except:
        return 0.0

async def fill_date(page, selector, value):
    """Preenche campo de data de forma robusta."""
    try:
        el = await page.wait_for_selector(selector, timeout=3000)
        await el.click(click_count=3)
        await el.type(value, delay=50)
    except:
        pass

async def scrape_cidade(page, cidade, primeiro_dia, ultimo_dia):
    print(f"\n→ {cidade['nome']}: conectando...")
    dados = []
    try:
        # 1. Login
        await page.goto(cidade["url"], timeout=25000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        # Preencher credenciais
        for sel in ['input[name="usuario"]', 'input[name="user"]', 'input[type="text"]:visible']:
            try:
                await page.fill(sel, USUARIO, timeout=2000)
                break
            except: pass

        for sel in ['input[name="senha"]', 'input[name="password"]', 'input[type="password"]:visible']:
            try:
                await page.fill(sel, SENHA, timeout=2000)
                break
            except: pass

        for sel in ['input[type="submit"]', 'button[type="submit"]', 'button:has-text("Entrar")', 'button:has-text("Login")']:
            try:
                await page.click(sel, timeout=2000)
                break
            except: pass

        await page.wait_for_load_state("networkidle", timeout=20000)
        await page.wait_for_timeout(1000)
        print(f"   ✓ Login OK — URL: {page.url}")

        # 2. Navegar para Finanças → Demonstrativo
        nav_ok = False
        try:
            await page.click('a:has-text("Finanças"), span:has-text("Finanças"), li:has-text("Finanças")', timeout=5000)
            await page.wait_for_timeout(800)
            await page.click('a:has-text("Demonstrativo"), span:has-text("Demonstrativo")', timeout=5000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            nav_ok = True
        except:
            pass

        if not nav_ok:
            base = cidade["url"].rstrip("/")
            for path in ["/financeiro/demonstrativo", "/financeiro", "/relatorios/demonstrativo"]:
                try:
                    await page.goto(base + path, timeout=15000, wait_until="domcontentloaded")
                    nav_ok = True
                    break
                except: pass

        await page.wait_for_timeout(1500)
        print(f"   ✓ Financeiro: {page.url}")

        # 3. Selecionar Pix Doutores no select de método
        metodo_ok = False
        for sel in [
            'select[name="metodo"]',
            'select[name="metodo_pagamento"]',
            'select[name="forma_pagamento"]',
            'select[name="tipo"]',
            'select:has-option("Pix Doutores")',
            'select',
        ]:
            try:
                await page.select_option(sel, label="Pix Doutores", timeout=3000)
                metodo_ok = True
                print(f"   ✓ Método selecionado via: {sel}")
                break
            except: pass

        if not metodo_ok:
            # Tenta pelo value
            for sel in ['select[name="metodo"]', 'select[name="metodo_pagamento"]', 'select']:
                try:
                    options = await page.eval_on_selector_all(f'{sel} option', 'opts => opts.map(o => ({v: o.value, t: o.text}))')
                    for opt in options:
                        if 'pix' in opt['t'].lower() and 'doutor' in opt['t'].lower():
                            await page.select_option(sel, value=opt['v'], timeout=2000)
                            metodo_ok = True
                            print(f"   ✓ Método selecionado por value: {opt['v']}")
                            break
                    if metodo_ok:
                        break
                except: pass

        await page.wait_for_timeout(500)

        # 4. Preencher datas (primeiro dia e último dia do mês)
        date_pairs = [
            ('input[name="data_ini"]', 'input[name="data_fim"]'),
            ('#data_ini', '#data_fim'),
            ('input[name="inicio"]', 'input[name="fim"]'),
            ('input[name="de"]', 'input[name="ate"]'),
            ('input[placeholder*="nicio"]', 'input[placeholder*="im"]'),
            ('input[type="date"]:first-of-type', 'input[type="date"]:last-of-type'),
        ]
        date_ok = False
        for sel_ini, sel_fim in date_pairs:
            try:
                # Verifica se o campo existe
                ini_el = await page.wait_for_selector(sel_ini, timeout=2000)
                fim_el = await page.wait_for_selector(sel_fim, timeout=2000)

                # Verifica se é input[type=date] (formato yyyy-mm-dd) ou texto (dd/mm/yyyy)
                ini_type = await ini_el.get_attribute('type')
                if ini_type == 'date':
                    # Converter para yyyy-mm-dd
                    d1 = datetime.datetime.strptime(primeiro_dia, "%d/%m/%Y").strftime("%Y-%m-%d")
                    d2 = datetime.datetime.strptime(ultimo_dia,   "%d/%m/%Y").strftime("%Y-%m-%d")
                    await ini_el.fill(d1)
                    await fim_el.fill(d2)
                else:
                    await ini_el.click(click_count=3)
                    await ini_el.type(primeiro_dia, delay=30)
                    await fim_el.click(click_count=3)
                    await fim_el.type(ultimo_dia, delay=30)

                date_ok = True
                print(f"   ✓ Datas preenchidas: {primeiro_dia} → {ultimo_dia}")
                break
            except: pass

        if not date_ok:
            print(f"   ⚠ Campos de data não encontrados")

        await page.wait_for_timeout(500)

        # 5. Clicar em Buscar
        for sel in [
            'button:has-text("Buscar")',
            'input[value="Buscar"]',
            'button:has-text("Filtrar")',
            'button:has-text("Pesquisar")',
            'input[type="submit"]',
        ]:
            try:
                await page.click(sel, timeout=3000)
                break
            except: pass

        await page.wait_for_load_state("networkidle", timeout=20000)
        await page.wait_for_timeout(2000)
        print(f"   ✓ Busca executada")

        # 6. Extrair dados da tabela
        dados = await page.evaluate("""
            () => {
                const rows = [];
                document.querySelectorAll('table tr').forEach(tr => {
                    const cells = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
                    if (cells.length < 4) return;
                    // Linha com data dd/mm/yyyy
                    if (!/^\d{2}\/\d{2}\/\d{4}/.test(cells[0])) return;
                    // Deve conter 'Pix Doutores' em alguma célula
                    const linha = cells.join('|').toLowerCase();
                    if (!linha.includes('pix') || !linha.includes('doutor')) return;

                    rows.push({
                        data:       cells[0] || '',
                        metodo:     cells[1] || '',
                        origem:     cells[2] || '',
                        valor:      cells[3] || '0',
                        valor_desc: cells[4] || cells[3] || '0',
                        nf:         cells[7] || cells[6] || '',
                        saldo:      cells[8] || cells[7] || '',
                    });
                });
                return rows;
            }
        """)

        print(f"   ✓ {len(dados)} lançamentos encontrados")

    except PWTimeout as e:
        print(f"   ✗ TIMEOUT: {e}")
    except Exception as e:
        print(f"   ✗ ERRO: {e}")

    # Processar registros
    resultado = []
    for row in dados:
        origem = row.get("origem", "")
        m = re.match(r"Recebido de (.+?)(?:\s+Pago por:|$)", origem, re.IGNORECASE)
        paciente = m.group(1).strip() if m else origem
        m2 = re.search(r"Pago por:\s*(.+)", origem, re.IGNORECASE)
        responsavel = m2.group(1).strip() if m2 else "O paciente"

        resultado.append({
            "data":        row["data"],
            "cidade":      cidade["nome"],
            "paciente":    paciente,
            "responsavel": responsavel,
            "valor":       parse_valor(row["valor"]),
            "nf":          (row.get("nf") or "").strip(),
            "origem_raw":  origem,
        })

    return resultado


async def main():
    primeiro, ultimo, mes_ref = get_periodo()
    print(f"=== Top Estética Bucal — Scraper PIX Doutores ===")
    print(f"Período: {primeiro} → {ultimo}  |  Mês: {mes_ref}")

    todos = []
    erros = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )

        for cidade in CIDADES:
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            try:
                registros = await scrape_cidade(page, cidade, primeiro, ultimo)
                todos.extend(registros)
            except Exception as e:
                erros.append({"cidade": cidade["nome"], "erro": str(e)})
                print(f"  ✗ Falha geral {cidade['nome']}: {e}")
            finally:
                await page.close()
                await context.close()

        await browser.close()

    output = {
        "gerado_em":  datetime.datetime.now().isoformat(),
        "mes_ref":    mes_ref,
        "total_regs": len(todos),
        "cidades_ok": len(CIDADES) - len(erros),
        "erros":      erros,
        "dados":      todos,
    }

    with open("dados.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n=== Concluído: {len(todos)} registros | {len(erros)} erros ===")
    if erros:
        for e in erros:
            print(f"  ✗ {e['cidade']}: {e['erro']}")

if __name__ == "__main__":
    asyncio.run(main())

