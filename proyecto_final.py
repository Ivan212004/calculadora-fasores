# -*- coding: utf-8 -*-
"""
PracticNupNup - NumLavPro Versión FINAL (Corregida v5)
- Añade salto de página en PDF para el fasor.
- Expone el servidor a la red local (0.0.0.0).
"""

# 1. Imports
from flask import Flask, request, jsonify, render_template_string, send_file
import numpy as np
import cmath, math, io, base64, os, time
# (Se eliminó 'import tempfile')
from reportlab.lib.pagesizes import A4
# ########## MODIFICADO: Se añade PageBreak ##########
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 2. Configuración de Flask
app = Flask(__name__)

# 3. Configuración del Programa
MAX_SIZE = 20
DEFAULT_SIZE = 7
PDF_TITLE = "NumLavPro - Reporte de resultados"

# 4. Funciones de Utilidad (Parseo de Complejos)
def parse_complex(s):
    if s is None: raise ValueError("Celda vacía")
    original = str(s).strip()
    if original == '': raise ValueError("Celda vacía")
    s = original.replace(' ', '').replace('−', '-')
    if '∠' in s:
        try:
            parts = s.split('∠')
            mag = float(parts[0])
            ang_str = parts[1].replace('°','')
            ang_deg = float(ang_str)
            ang_rad = math.radians(ang_deg)
            return cmath.rect(mag, ang_rad)
        except Exception:
            raise ValueError(f"Formato polar inválido: '{original}'")
    s = s.replace('+j', '+1j').replace('-j', '-1j')
    if s == 'j': s = '1j'
    if s == '-j': s = '-1j'
    try:
        return complex(s)
    except Exception:
        raise ValueError(f"Formato complejo inválido: '{original}'")

def format_rect(z, precision=6):
    z = complex(z)
    if abs(z.imag) < 1e-12: return f"{z.real:+.{precision}f}"
    if abs(z.real) < 1e-12: return f"{z.imag:+.{precision}f}j"
    sign = '+' if z.imag >= 0 else '-'
    return f"{z.real:+.{precision}f} {sign} {abs(z.imag):.{precision}f}j"

def rect_to_polar(z):
    z = complex(z)
    mag = abs(z)
    ang = math.degrees(cmath.phase(z))
    return mag, ang

# 5. Ejemplos de Circuitos
def example_rlc_series(n=3):
    if n < 2: n = 2
    A = [["0" for _ in range(n)] for __ in range(n)]
    b = ["0" for _ in range(n)]
    for i in range(n):
        R = 5 + i*1.0
        XL = 2 + 0.5*i
        XC = 1/(2*math.pi*60*(1+0.1*i))
        Z = complex(R, XL - XC)
        A[i][i] = f"{Z.real:.6f}{Z.imag:+.6f}j"
        if i+1 < n:
            A[i][i+1] = "-1"
            A[i+1][i] = "1"
    b[0] = "120∠0"
    return A, b, "Ejemplo RLC serie"

def example_ac(n=3):
    A = [["0" for _ in range(n)] for __ in range(n)]
    b = ["0" for _ in range(n)]
    for i in range(n):
        A[i][i] = f"{(10 + i):.6f}+{(0.5*i):.6f}j"
        if i+1 < n:
            A[i][i+1] = f"{(-1.5):.6f}+{(0.2):.6f}j"
            A[i+1][i] = f"{(0.7):.6f}-{(0.3):.6f}j"
    b[0] = "230∠0"
    if n>1: b[1] = "0"
    return A, b, "Ejemplo AC"

def example_trifasico():
    A = [["10+5j", "0", "0"], ["0", "10+5j", "0"], ["0", "0", "10+5j"]]
    b = ["120∠0", "120∠-120", "120∠120"]
    return A, b, "Ejemplo trifásico"

# 6. Lógica del Solucionador
def validate_and_build_A_b(A_strings, b_strings):
    if not isinstance(A_strings, list) or not A_strings:
        raise ValueError("Matriz A vacía")
    n = len(A_strings)
    for row in A_strings:
        if len(row) != n: raise ValueError("A debe ser cuadrada (n x n)")
    if len(b_strings) != n: raise ValueError("Vector b debe tener tamaño n")
    A = np.zeros((n,n), dtype=complex)
    b = np.zeros(n, dtype=complex)
    for i in range(n):
        for j in range(n):
            try: A[i,j] = parse_complex(A_strings[i][j])
            except Exception as e: raise ValueError(f"Error en A[{i+1},{j+1}]: {e}")
    for i in range(n):
        try: b[i] = parse_complex(b_strings[i])
        except Exception as e: raise ValueError(f"Error en b[{i+1}]: {e}")
    if abs(np.linalg.det(A)) < 1e-14:
        raise ValueError("Determinante cero (matriz singular)")
    return A, b

def solve_system(A, b, method='auto'):
    A = np.array(A, dtype=complex)
    b = np.array(b, dtype=complex)
    n = A.shape[0]
    if method == 'auto': method = 'cramer' if n <= 4 else 'gauss'
    if method == 'cramer':
        detA = np.linalg.det(A)
        if abs(detA) < 1e-14: raise np.linalg.LinAlgError("Determinante cero")
        x = np.zeros(n, dtype=complex)
        for i in range(n):
            Ai = A.copy()
            Ai[:,i] = b
            x[i] = np.linalg.det(Ai) / detA
        return x
    elif method == 'gauss':
        return np.linalg.solve(A,b)
    else:
        raise ValueError("Método desconocido")

# 7. Gráfico Fasorial (Matplotlib)
def make_fasor_png(currents, title="Fasores de corrientes"):
    I = np.array(currents, dtype=complex)
    if I.size == 0:
        fig, ax = plt.subplots(figsize=(4,3))
        ax.text(0.5, 0.5, "Sin datos", ha='center', va='center')
        ax.axis('off')
    else:
        mags = np.abs(I)
        maxr = max(1e-6, np.max(mags)) * 1.2
        fig, ax = plt.subplots(figsize=(5,5))
        ax.set_aspect('equal', 'box')
        ax.set_xlim(-maxr, maxr)
        ax.set_ylim(-maxr, maxr)
        ax.axhline(0, color="#999", linewidth=0.6)
        ax.axvline(0, color="#999", linewidth=0.6)
        colors = plt.cm.tab10.colors
        for idx, z in enumerate(I):
            ax.arrow(0, 0, z.real, z.imag, head_width=maxr*0.03, head_length=maxr*0.05,
                     length_includes_head=True, color=colors[idx % len(colors)], linewidth=2)
            mag, ang = rect_to_polar(z)
            ax.text(z.real*1.05, z.imag*1.05, f"I{idx+1}\n{mag:.3f}∠{ang:.1f}°", fontsize=9)
        ax.set_title(title)
        ax.grid(True, linestyle=':', alpha=0.5)
        plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

# 8. Generador de PDF (ReportLab)
def create_pdf_bytes(A_strings, b_strings, x_solution, fasor_png_bytes, A_numpy, b_numpy, title=PDF_TITLE):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    
    if 'Code' not in styles:
        styles.add(ParagraphStyle(name='Code', parent=styles['Normal'], fontName='Courier'))
    
    story = []
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"Generado: {time.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Matriz A (Impedancias)", styles['Heading3']))
    story.append(Table(A_strings, hAlign='LEFT'))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Vector b (Fuentes)", styles['Heading3']))
    story.append(Table([[v] for v in b_strings], hAlign='LEFT'))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Resultados (Corrientes)", styles['Heading3']))
    rows = [["Nombre", "Rectangular", "|I| (Mag)", "Fase (°)"]]
    for i, xi in enumerate(x_solution): 
        mag, ang = rect_to_polar(xi)
        rows.append([f"I{i+1}", format_rect(xi, precision=6), f"{mag:.6f}", f"{ang:.4f}"])
    story.append(Table(rows, hAlign='LEFT'))
    story.append(Spacer(1, 8*mm))

    if A_numpy is not None and A_numpy.shape == (2, 2):
        story.append(Paragraph("Procedimiento (Regla de Cramer 2x2)", styles['Heading3']))
        story.append(Spacer(1, 4*mm))
        a, b = A_numpy[0, 0], A_numpy[0, 1]
        c, d = A_numpy[1, 0], A_numpy[1, 1]
        v1, v2 = b_numpy[0], b_numpy[1]
        det_A = (a * d) - (b * c)
        det_A1 = (v1 * d) - (b * v2)
        det_A2 = (a * v2) - (v1 * c)
        story.append(Paragraph("<b>1. Determinante General (Δ)</b>", styles['Normal']))
        story.append(Paragraph("Δ = (A[0,0] * A[1,1]) - (A[0,1] * A[1,0])", styles['Code']))
        story.append(Paragraph(f"Δ = ({format_rect(a, 3)}) * ({format_rect(d, 3)}) - ({format_rect(b, 3)}) * ({format_rect(c, 3)})", styles['Code']))
        story.append(Paragraph(f"<b>Δ = {format_rect(det_A, 6)}</b>", styles['Code']))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("<b>2. Determinante I1 (Δ1)</b>", styles['Normal']))
        story.append(Paragraph("Δ1 = (b[0] * A[1,1]) - (A[0,1] * b[1])", styles['Code']))
        story.append(Paragraph(f"Δ1 = ({format_rect(v1, 3)}) * ({format_rect(d, 3)}) - ({format_rect(b, 3)}) * ({format_rect(v2, 3)})", styles['Code']))
        story.append(Paragraph(f"<b>Δ1 = {format_rect(det_A1, 6)}</b>", styles['Code']))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("<b>3. Determinante I2 (Δ2)</b>", styles['Normal']))
        story.append(Paragraph("Δ2 = (A[0,0] * b[1]) - (b[0] * A[1,0])", styles['Code']))
        story.append(Paragraph(f"Δ2 = ({format_rect(a, 3)}) * ({format_rect(v2, 3)}) - ({format_rect(v1, 3)}) * ({format_rect(c, 3)})", styles['Code']))
        story.append(Paragraph(f"<b>Δ2 = {format_rect(det_A2, 6)}</b>", styles['Code']))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("<b>4. Soluciones Finales</b>", styles['Normal']))
        story.append(Paragraph(f"I1 = Δ1 / Δ = {format_rect(x_solution[0], 6)}", styles['Code']))
        story.append(Paragraph(f"I2 = Δ2 / Δ = {format_rect(x_solution[1], 6)}", styles['Code']))
        story.append(Spacer(1, 8*mm))

    if fasor_png_bytes is not None:
        try:
            # ########## MODIFICADO: Se añade el PageBreak() ##########
            story.append(PageBreak()) 
            story.append(Paragraph("Diagrama Fasorial", styles['Heading3']))
            story.append(Spacer(1, 4*mm))
            fasor_png_bytes.seek(0) 
            img = Image(fasor_png_bytes, width=140*mm, height=140*mm)
            img.hAlign = 'CENTER'
            story.append(img)
        except Exception as e:
            story.append(Paragraph(f"Error al insertar imagen Fasor: {e}", styles['Normal']))
                
    doc.build(story)
    buf.seek(0)
    return buf

# 9. Plantilla HTML (Frontend)
HTML_TEMPLATE = """
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>NumLavPro - PracticNupNup</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
      body { padding: 18px; }
      .matrix-input { width: 100px; font-family: monospace; }
      .small-note { font-size:0.9rem; color: #666; }
      .fasor-img { max-width: 100%; height: auto; border:1px solid #ddd; padding:6px; background:#fff; }
      #resultsArea {
        min-height:180px; 
        font-family: Consolas, monospace; 
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 10px;
        white-space: pre;
        overflow-x: auto;
      }
    </style>
  </head>
  <body class="bg-light">
    <div class="container">
      <div class="card shadow-sm">
        <div class="card-body">
          <h3 class="card-title">NumLavPro — PracticNupNup</h3>
          <p class="small-note">Introduzca impedancias (ej: 3+0.58j, -1.5j, 120∠0). Máx: {{max_size}}x{{max_size}}</p>
          <div class="controls row g-2 align-items-center">
            <div class="col-auto">
              <label class="form-label">Tamaño (n x n)</label>
              <input id="nSize" class="form-control" type="number" value="{{default_size}}" min="1" max="{{max_size}}" style="width:110px;">
            </div>
            <div class="col-auto">
              <label class="form-label">Método</label>
              <select id="methodSelect" class="form-select">
                <option value="auto">Auto</option>
                <option value="cramer">Cramer</option>
                <option value="gauss">Gauss</option>
              </select>
            </div>
            <div class="col-auto">
              <label class="form-label">AutoSolve</label><br>
              <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" id="autoSolveSwitch" checked>
                <label class="form-check-label" for="autoSolveSwitch">ON / OFF</label>
              </div>
            </div>
            <div class="col-auto">
              <label class="form-label">&nbsp;</label><br>
              <button id="genBtn" class="btn btn-primary">Generar</button>
              <button id="solveBtn" class="btn btn-success">Resolver</button>
              <button id="pdfBtn" class="btn btn-outline-secondary">Exportar PDF</button>
            </div>
            <div class="col-auto ms-auto text-end">
              <label class="form-label">Ejemplos</label><br>
              <div class="btn-group" role="group">
                <button class="btn btn-sm btn-info" onclick="loadExample('rlc')">RLC</button>
                <button class="btn btn-sm btn-info" onclick="loadExample('ac')">AC</button>
                <button class="btn btn-sm btn-info" onclick="loadExample('trif')">Trifásico</button>
              </div>
            </div>
          </div>
          <form id="matrixForm" class="mt-3">
            <div id="matrixArea"></div>
          </form>
          <hr>
          <div class="row">
            <div class="col-md-7">
              <h5>Resultados</h5>
              <div id="resultsArea"></div>
            </div>
            <div class="col-md-5">
              <h5>Diagrama fasorial</h5>
              <div id="fasorArea" class="text-center">
                <img id="fasorImg" class="fasor-img" src="/fasor.png?ts=0" alt="Fasor">
              </div>
            </div>
          </div>
        </div>
      </div>
      <p class="text-muted mt-2 small">NumLavPro - PracticNupNup · Versión Definitiva (Corregida)</p>
    </div>

    <script>
      const maxSize = {{max_size}};
      let debounceTimer = null;
      const debounceDelay = 700;

      function makeMatrix(n) {
        const cont = document.getElementById('matrixArea');
        cont.innerHTML = '';
        let html = '';
        html += '<div class="mb-2"><label class="form-label">Matriz A (impedancias)</label>';
        html += '<table class="table table-bordered table-striped table-hover table-dark"><tbody>';
        for (let i=0;i<n;i++){
          html += '<tr>';
          for (let j=0;j<n;j++){
            html += '<td><input class="form-control matrix-input" name="A_' + i + '_' + j + '" value="0"></td>';
          }
          html += '</tr>';
        }
        html += '</tbody></table></div>';
        html += '<div class="mb-2"><label class="form-label">Vector b (fuentes)</label>';
        html += '<table class="table table-bordered table-striped"><tbody>';
        for (let i=0;i<n;i++){
          html += '<tr><td>V' + (i+1) + '</td><td><input class="form-control matrix-input" name="b_' + i + '" value="0"></td></tr>';
        }
        html += '</tbody></table></div>';
        cont.innerHTML = html;
        setInputChangeHandlers();
      }

      function setInputChangeHandlers() {
        const inputs = document.querySelectorAll('#matrixArea input');
        inputs.forEach(function(inp) {
          inp.addEventListener('input', function() {
            if (document.getElementById('autoSolveSwitch').checked) {
              if (debounceTimer) clearTimeout(debounceTimer);
              debounceTimer = setTimeout(function() {
                doSolve(false);
              }, debounceDelay);
            }
          });
        });
      }

      function collectForm() {
        const n = parseInt(document.getElementById('nSize').value || 3);
        const A = [];
        const b = [];
        for (let i=0; i<n; i++){
          const row = [];
          for (let j=0; j<n; j++){
            const el = document.querySelector('[name="A_' + i + '_' + j + '"]');
            row.push(el ? el.value : "");
          }
          A.push(row);
        }
        for (let i=0; i<n; i++){
          const el = document.querySelector('[name="b_' + i + '"]');
          b.push(el ? el.value : "");
        }
        return {matrix: A, vector: b, method: document.getElementById('methodSelect').value};
      }

      async function loadExample(type) {
        const n = parseInt(document.getElementById('nSize').value || {{default_size}});
        try {
            const res = await fetch('/example/' + type + '?n=' + n);
            const data = await res.json();
            if (data.error) {
              alert("Error cargando ejemplo: " + data.error);
              return;
            }
            const A = data.matrix;
            const b = data.vector;
            document.getElementById('nSize').value = A.length;
            makeMatrix(A.length);
            for (let i=0;i<A.length;i++){
              for (let j=0;j<A.length;j++){
                const el = document.querySelector('[name="A_' + i + '_' + j + '"]');
                if (el) el.value = A[i][j];
              }
              const elb = document.querySelector('[name="b_' + i + '"]');
              if (elb) elb.value = b[i];
            }
            if (document.getElementById('autoSolveSwitch').checked) {
              doSolve(false);
            }
        } catch (e) {
            alert("Error de conexión al cargar ejemplo: " + e.message);
        }
      }

      async function doSolve(downloadPdf) {
        if (downloadPdf === undefined) { downloadPdf = false; }
        const payload = collectForm();
        const out = document.getElementById('resultsArea');
        try {
            const res = await fetch('/solve', {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify(payload)
            });
            if (!res.ok) {
              const err = await res.json();
              out.textContent = "ERROR: " + (err.error || JSON.stringify(err));
              return;
            }
            const data = await res.json();
            let s = "";
            data.result.forEach(function(el, idx) {
              s += 'I' + (idx+1) + ' = ' + el.rect + ' A    |  |I|=' + el.mag.toFixed(6) + ' A  ∠ ' + el.angle.toFixed(4) + '°\\n';
            });
            s += "\\nVerificación (A·I):\\n";
            data.vcalc.forEach(function(v, i) {
              s += 'Malla ' + (i+1) + ': ' + v + '\\n';
            });
            out.textContent = s;
            const img = document.getElementById('fasorImg');
            img.src = '/fasor.png?ts=' + Date.now();
            if (downloadPdf) {
              window.location.href = '/download_pdf?ts=' + Date.now();
            }
        } catch (e) {
            out.textContent = "ERROR de conexión: " + e.message;
        }
      }

      document.getElementById('genBtn').addEventListener('click', function() {
        const n = Math.min(maxSize, Math.max(1, parseInt(document.getElementById('nSize').value || 3)));
        document.getElementById('nSize').value = n;
        makeMatrix(n);
      });
      document.getElementById('solveBtn').addEventListener('click', function() { doSolve(false); });
      document.getElementById('pdfBtn').addEventListener('click', function() { doSolve(true); });

      document.addEventListener('DOMContentLoaded', function() {
        const initialN = {{default_size}};
        makeMatrix(initialN);
      });
    </script>
  </body>
</html>
"""

# 11. Endpoints (Rutas) de la API de Flask
LAST = {"A_strings": None, "b_strings": None, "x": None, "fasor_bytes": None, "A_numpy": None, "b_numpy": None}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, max_size=MAX_SIZE, default_size=DEFAULT_SIZE)

@app.route('/example/<tipo>')
def example_route(tipo):
    try:
        n = int(request.args.get('n', DEFAULT_SIZE))
        if n < 1 or n > MAX_SIZE:
            return jsonify({"error":"Tamaño n inválido"}), 400
        if tipo == 'rlc': A,b,desc = example_rlc_series(n)
        elif tipo == 'ac': A,b,desc = example_ac(n)
        elif tipo == 'trif': A,b,desc = example_trifasico()
        else: return jsonify({"error":"Tipo de ejemplo desconocido"}), 404
        return jsonify({"matrix": A, "vector": b, "desc": desc})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/solve', methods=['POST'])
def solve_route():
    try:
        data = request.get_json()
        A_strings = data.get('matrix')
        b_strings = data.get('vector')
        method = data.get('method', 'auto')
        A, b = validate_and_build_A_b(A_strings, b_strings)
        x = solve_system(A, b, method=method)
        pretty_results = []
        for xi in x:
            rect = format_rect(xi, precision=8)
            mag, ang = rect_to_polar(xi)
            pretty_results.append({"rect": rect, "mag": mag, "angle": ang})
        Vcalc = (A @ x).tolist()
        Vcalc_str = [format_rect(v, precision=6) for v in Vcalc]
        fasor_buf = make_fasor_png(x, title="Fasores de Corriente")
        LAST['A_strings'] = A_strings
        LAST['b_strings'] = b_strings
        LAST['x'] = x
        LAST['fasor_bytes'] = fasor_buf.getvalue()
        LAST['A_numpy'] = A
        LAST['b_numpy'] = b
        return jsonify({"result": pretty_results, "vcalc": Vcalc_str})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/fasor.png')
def fasor_png():
    if LAST.get('fasor_bytes') is None:
        buf = make_fasor_png(np.array([]), title="Sin datos")
        return send_file(buf, mimetype='image/png')
    else:
        return send_file(io.BytesIO(LAST['fasor_bytes']), mimetype='image/png')

@app.route('/download_pdf')
def download_pdf():
    if LAST.get('x') is None:
        return "No hay solución para exportar. Resuelve primero.", 400
    try:
        pdf_bytes_io = create_pdf_bytes(
            LAST['A_strings'], 
            LAST['b_strings'], 
            LAST['x'], 
            io.BytesIO(LAST['fasor_bytes']) if LAST['fasor_bytes'] else None,
            LAST['A_numpy'],
            LAST['b_numpy']
        )
        return send_file(
            pdf_bytes_io, 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name='NumLavPro_reporte.pdf'
        )
    except Exception as e:
        return f"Error generando PDF: {e}", 500

# 12. Punto de Entrada Principal
if __name__ == "__main__":
    print("================================================================")
    print("Iniciando NumLavPro / PracticNupNup (Versión Definitiva)")
    print(f"Servidor corriendo en http://127.0.0.1:5000 y en tu IP local.")
    print("Presiona CTRL+C para detener.")
    print("================================================================")
    # ########## MODIFICADO: Se añade host='0.0.0.0' ##########
    app.run(debug=True, port=5000, use_reloader=True, host='0.0.0.0')