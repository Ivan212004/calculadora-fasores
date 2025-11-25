# -*- coding: utf-8 -*-
"""
PracticNupNup - NumLavPro Versión FINAL (Corregida v5)
- FASE 1: Modo Dual (Mallas/Nodos)
- FASE 2: Ayudante de Componentes (con Z/Y, G, Γ, D, Fracciones)
- FASE 3: Añadido Modal de Ayuda y Pie de Página
- FASE 3.1: "Purificación" de UI (Estilo Apple-like)
- FASE 3.2: Título Centrado y Responsividad Móvil
- FASE 3.3: Nombre "CircuitSolve" y Nuevo Diseño de Matriz (Gris)
- FASE 3.4: Layout A|b, Zoom de Fasor, Botones Dinámicos
- FASE 3.5: Corregido un typo fatal (value__) en el HTML
### FASE 3.7: Corregidos typos (value__, ts='D, 4d), DEFAULT_SIZE=2, y Resultados en Columnas ###
"""

# 1. Imports
from flask import Flask, request, jsonify, render_template_string, send_file
import numpy as np
import cmath, math, io, base64, os, time
from reportlab.lib.pagesizes import A4
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
### FASE 3.7 - MODIFICADO ###
DEFAULT_SIZE = 2
PDF_TITLE = "NumLavPro - Reporte de resultados"

# 4. Funciones de Utilidad (Parseo de Complejos)
# ... (Sin cambios) ...
def parse_complex(s):
    if s is None: raise ValueError("Celda vacía")
    original = str(s).strip()
    if original == '': raise ValueError("Celda vacía")
    s = original.replace(' ', '').replace('−', '-')

    is_simple_fraction = (
        '/' in s and 
        'j' not in s and 
        '∠' not in s and 
        ('+' not in s[1:]) and 
        ('-' not in s[1:])
    )
    
    if is_simple_fraction:
        try:
            parts = s.split('/')
            if len(parts) == 2:
                num = float(parts[0])
                den = float(parts[1])
                if den == 0:
                    raise ValueError("División por cero en fracción")
                return num / den
        except Exception:
            pass

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

### FASE 3.7 - MODIFICADO ### Precisión por defecto a 4
def format_rect(z, precision=4):
    z = complex(z)
    if abs(z.imag) < 1e-12: 
        if abs(z.real) < 1e-12: return f"{0.0:+.{precision}f}"
        return f"{z.real:+.{precision}f}"
    if abs(z.real) < 1e-12: 
        if abs(z.imag) < 1e-12: return f"{0.0:+.{precision}f}"
        return f"{z.imag:+.{precision}f}j"
    sign = '+' if z.imag >= 0 else '-'
    return f"{z.real:+.{precision}f} {sign} {abs(z.imag):.{precision}f}j"

def rect_to_polar(z):
    z = complex(z)
    mag = abs(z)
    ang = math.degrees(cmath.phase(z))
    return mag, ang

# 5. Ejemplos de Circuitos
# ... (Sin cambios) ...
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
# ... (Sin cambios) ...
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
# ... (Sin cambios) ...
def make_fasor_png(currents, mode="mallas"):
    I = np.array(currents, dtype=complex)
    label_pref = "I" if mode == 'mallas' else "V"
    plot_title = "Fasores de Corriente" if mode == 'mallas' else "Fasores de Voltaje"
    
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
            ax.text(z.real*1.05, z.imag*1.05, f"{label_pref}{idx+1}\n{mag:.3f}∠{ang:.1f}°", fontsize=9)
        
        ax.set_title(plot_title)
        ax.grid(True, linestyle=':', alpha=0.5)
        plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return buf

# 8. Generador de PDF (ReportLab)
# ... (Sin cambios) ...
def create_pdf_bytes(A_strings, b_strings, x_solution, fasor_png_bytes, A_numpy, b_numpy, mode="mallas", title=PDF_TITLE):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    
    if 'Code' not in styles:
        styles.add(ParagraphStyle(name='Code', parent=styles['Normal'], fontName='Courier'))
    
    if mode == 'nodos':
        label_mat_a = "Matriz A (Admitancias)"
        label_vec_b = "Vector b (Fuentes de Corriente)"
        label_resultados = "Resultados (Voltajes de Nodo)"
        label_res_pref = "V"
        label_fasor = "Diagrama Fasorial (Voltajes)"
        label_proc_pref = "V"
    else: # default to mallas
        label_mat_a = "Matriz A (Impedancias)"
        label_vec_b = "Vector b (Fuentes de Voltaje)"
        label_resultados = "Resultados (Corrientes)"
        label_res_pref = "I"
        label_fasor = "Diagrama Fasorial (Corrientes)"
        label_proc_pref = "I"
    
    story = []
    story.append(Paragraph(f"CircuitSolve - Reporte de {label_resultados.split(' ')[1]}", styles['Title']))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f"Generado: {time.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph(label_mat_a, styles['Heading3']))
    story.append(Table(A_strings, hAlign='LEFT'))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(label_vec_b, styles['Heading3']))
    story.append(Table([[v] for v in b_strings], hAlign='LEFT'))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(label_resultados, styles['Heading3']))
    rows = [["Nombre", "Rectangular", f"|{label_res_pref}| (Mag)", "Fase (°)"]]
    for i, xi in enumerate(x_solution): 
        mag, ang = rect_to_polar(xi)
        rows.append([f"{label_res_pref}{i+1}", format_rect(xi, precision=4), f"{mag:.4f}", f"{ang:.4f}"])
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
        story.append(Paragraph(f"<b>2. Determinante {label_proc_pref}1 (Δ1)</b>", styles['Normal']))
        story.append(Paragraph("Δ1 = (b[0] * A[1,1]) - (A[0,1] * b[1])", styles['Code']))
        story.append(Paragraph(f"Δ1 = ({format_rect(v1, 3)}) * ({format_rect(d, 3)}) - ({format_rect(b, 3)}) * ({format_rect(v2, 3)})", styles['Code']))
        story.append(Paragraph(f"<b>Δ1 = {format_rect(det_A1, 6)}</b>", styles['Code']))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph(f"<b>3. Determinante {label_proc_pref}2 (Δ2)</b>", styles['Normal']))
        story.append(Paragraph("Δ2 = (A[0,0] * b[1]) - (b[0] * A[1,0])", styles['Code']))
        story.append(Paragraph(f"Δ2 = ({format_rect(a, 3)}) * ({format_rect(v2, 3)}) - ({format_rect(v1, 3)}) * ({format_rect(c, 3)})", styles['Code']))
        story.append(Paragraph(f"<b>Δ2 = {format_rect(det_A2, 6)}</b>", styles['Code']))
        story.append(Spacer(1, 4*mm))
        story.append(Paragraph("<b>4. Soluciones Finales</b>", styles['Normal']))
        story.append(Paragraph(f"{label_proc_pref}1 = Δ1 / Δ = {format_rect(x_solution[0], 6)}", styles['Code']))
        story.append(Paragraph(f"{label_proc_pref}2 = Δ2 / Δ = {format_rect(x_solution[1], 6)}", styles['Code']))
        story.append(Spacer(1, 8*mm))

    if fasor_png_bytes is not None:
        try:
            story.append(PageBreak()) 
            story.append(Paragraph(label_fasor, styles['Heading3']))
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
    <title>CircuitSolve - Análisis de Circuitos AC</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    
    <style>
      /* 1. Fuente y Fondo */
      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        background-color: #f5f5f7;
        padding: 32px 18px;
      }

      /* 2. Tarjeta principal más suave */
      .card {
        border: none;
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
      }
      
      /* 3. Tipografía más limpia */
      .card-title {
        font-weight: 600;
        letter-spacing: -0.5px;
      }
      h5, h6, .accordion-button {
        font-weight: 500;
      }
      h6 {
          margin-bottom: 0.5rem;
          color: #333;
      }

      /* 4. Botones "Premium" */
      .btn {
        border-radius: 12px;
        font-weight: 500;
        padding: 8px 16px;
      }
      .btn-sm {
        border-radius: 10px;
      }
      .btn-primary, .btn-primary.active {
        --bs-btn-bg: #007aff;
        --bs-btn-border-color: #007aff;
        --bs-btn-hover-bg: #0070e0;
        --bs-btn-hover-border-color: #0070e0;
        --bs-btn-active-bg: #0062c4;
        --bs-btn-active-border-color: #0062c4;
        --bs-btn-focus-shadow-rgb: 38, 132, 255;
      }
      .btn-outline-primary {
        --bs-btn-color: #007aff;
        --bs-btn-border-color: #007aff;
        --bs-btn-hover-bg: #007aff;
        --bs-btn-hover-border-color: #007aff;
        --bs-btn-active-bg: #007aff;
        --bs-btn-active-border-color: #007aff;
      }
      .btn-group .btn.active {
          z-index: 2;
      }
      
      /* 5. Acordeón más limpio */
      .accordion {
        --bs-accordion-border-radius: 12px;
        --bs-accordion-inner-border-radius: 12px;
        --bs-accordion-border-color: #e0e0e0;
      }
      .accordion-button {
        border-radius: 0;
      }
      .accordion-button:not(.collapsed) {
        background-color: #f0f7ff;
        color: #000;
        box-shadow: none;
      }
      .accordion-button:focus {
        box-shadow: none;
        border-color: transparent;
      }
      
      /* 6. Inputs y Selectores más suaves */
      .form-control, .form-select {
        border-radius: 10px;
        border-color: #d2d2d7;
        background-color: #fcfcfc;
      }
      .form-control:focus, .form-select:focus {
        border-color: #007aff;
        box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.25);
      }
      .component-helper .form-control-plaintext {
        background-color: #e8e8ed;
        border-radius: 8px;
        font-weight: 500;
      }

      /* 7. Estilos de la app original (Monospace, etc.) */
      .matrix-input { 
        width: 100px; 
        font-family: monospace;
        font-size: 0.95rem;
      }
      
      /* ### FASE 3.7 - MODIFICADO ### Estilos para Cajas de Resultados */
      .results-box {
        font-family: Consolas, monospace; 
        background-color: #f5f5f7;
        border: 1px solid #d2d2d7;
        border-radius: 12px;
        padding: 12px;
        white-space: pre;
        overflow-x: auto;
        min-height: 100px;
      }
      #verificationArea .results-box {
          min-height: 0;
          background-color: #fff; /* Fondo blanco para verificación */
      }
      /* Fin de Cajas */

      .fasor-img { 
        max-width: 100%; 
        height: auto; 
        border:1px solid #d2d2d7; 
        padding:6px; 
        background:#fff; 
        border-radius: 12px;
        cursor: zoom-in;
      }
      
      /* 8. Estilos que no se han tocado */
      .small-note { font-size:0.9rem; color: #555; }
      .unit-select { flex: 0 0 75px; }
      .copy-btn { flex: 0 0 90px; }
      .combined-label { font-weight: 500; margin-bottom: 0.25rem; font-size: 0.9rem; }
      .combined-calc-box { background-color: #fff; border: 1px solid #d2d2d7; border-radius: 12px; padding: 1rem; }
      .l-gamma-label { width: 40px; font-weight: bold; font-family: monospace; font-size: 1rem; }
      .help-list { padding-left: 1.2rem; }
      .help-list code { background-color: #e8e8ed; padding: 2px 5px; border-radius: 4px; font-size: 0.9rem; color: #d63384; }
      
      /* 9. Responsividad Móvil y Colores de Matriz */
      .table-responsive-wrapper {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        border-radius: 12px; 
        overflow: hidden; 
        border: 1px solid #d2d2d7; 
      }
      
      .table-striped > tbody > tr:nth-of-type(odd) > * {
        --bs-table-accent-bg: #f0f7ff;
        color: #000;
      }
      .table-bordered {
          border-color: #d2d2d7;
      }
      .table-hover > tbody > tr:hover > * {
        --bs-table-accent-bg: #e0e0e0;
      }
      .form-control.matrix-input {
          background-color: #fff;
          border-color: #d2d2d7;
      }
      .table-striped .form-control.matrix-input {
          background-color: #fcfcfc;
      }
      .form-control.matrix-input:focus {
        border-color: #007aff;
        box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.25);
      }
      
      #verificationAccordion .accordion-button {
          padding: 0.75rem 1.25rem;
          background-color: #f5f5f7;
          font-size: 0.9rem;
          color: #555;
          border-radius: 12px; /* Redondeado completo */
      }
      #verificationAccordion .accordion-button:not(.collapsed) {
          background-color: #e8e8ed;
          border-bottom-left-radius: 0;
          border-bottom-right-radius: 0;
      }
      #verificationAccordion .accordion-body {
          padding: 0;
          /* ### FASE 3.7 ### Aplicar estilo de caja a la verificación */
          background-color: #f5f5f7;
          border: 1px solid #d2d2d7;
          border-top: none;
          border-bottom-left-radius: 12px;
          border-bottom-right-radius: 12px;
          padding: 1rem;
      }
      #verificationAccordion .accordion-item {
          border: none; /* Quitar borde del acordeón de verificación */
      }
    </style>
  </head>
  <body class="bg-light">
    <div class="container">
      <div class="card shadow-sm">
        <div class="card-body p-4 p-md-5">
          
          <div class="text-center mb-4">
            <h3 class="card-title" style="font-weight: 700; font-size: 2.75rem; letter-spacing: -1px;">CircuitSolve</h3>
            <p class="text-muted" style="font-size: 1.1rem; margin-top: -5px;">Tu Asistente de Análisis de Circuitos AC</p>
          </div>
          
          <div class="mb-3 pt-3">
              <label class="form-label fw-bold">Modo de Análisis:</label>
              <div class="btn-group w-100" role="group">
                <button type="button" id="btnMallas" class="btn btn-primary active" onclick="setMode('mallas')">Mallas (Impedancias)</button>
                <button type="button" id="btnNodos" class="btn btn-outline-primary" onclick="setMode('nodos')">Nodos (Admitancias)</button>
              </div>
          </div>
          
          <div class="accordion mb-3" id="componentHelperAccordion">
            <div class="accordion-item">
              <h2 class="accordion-header">
                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseCombined" aria-expanded="true" aria-controls="collapseCombined" id="labelCombinedAccordion">
                  Elemento General tipo Serie
                </button>
              </h2>
              <div id="collapseCombined" class="accordion-collapse collapse show" data-bs-parent="#componentHelperAccordion">
                <div class="accordion-body component-helper">
                  <div class="input-group input-group-sm mb-3">
                    <span class="input-group-text">Frecuencia (f ó ω)</span>
                    <input type="text" class="form-control" value="60" id="freqInput">
                    <select class="form-select unit-select" id="freqType">
                      <option value="hz" selected>Hz</option>
                      <option value="rad">rad/s</option>
                    </select>
                  </div>
                  <div class="combined-calc-box">
                    <label class="combined-label" id="labelCombinedBox">Componentes en Serie (Modo Mallas)</label>
                    <div class="input-group input-group-sm">
                      <span class="input-group-text l-gamma-label" id="labelR_comb_text">R</span>
                      <input type="text" class="form-control" placeholder="Valor (ej. 10 o 1/15)" id="valR_comb">
                      <span class="input-group-text unit-select" id="labelR_comb_unit">Ω</span>
                    </div>
                    <div class="input-group input-group-sm">
                      <span class="input-group-text l-gamma-label" id="labelL_comb_text">L/Γ</span>
                      <input type="text" class="form-control" placeholder="Valor" id="valL_comb">
                      <select class="form-select unit-select" id="unitL_comb">
                        <option value="1/L">H</option>
                        <option value="1e-3/L" selected>mH</option>
                        <option value="1e-6/L">µH</option>
                        <option value="1/G">H⁻¹</option>
                        <option value="1e-3/G">mH⁻¹</option>
                        <option value="1e3/G">kH⁻¹</option>
                      </select>
                    </div>
                    <div class="input-group input-group-sm">
                      <span class="input-group-text l-gamma-label" id="labelC_comb_text">C/D</span>
                      <input type="text" class="form-control" placeholder="Valor (ej. 100 o 1/60)" id="valC_comb">
                      <select class="form-select unit-select" id="unitC_comb">
                        <option value="1/C">F</option>
                        <option value="1e-3/C">mF</option>
                        <option value="1e-6/C" selected>µF</option>
                        <option value="1e-9/C">nF</option>
                        <option value="1e-12/C">pF</option>
                        <option value="1/D">D</option>
                        <option value="1e-3/D">mD</option>
                        <option value="1e3/D">kD</option>
                      </select>
                    </div>
                    <div class="input-group input-group-sm mt-3">
                      <input type="text" readonly class="form-control form-control-plaintext" id="resultCombined" placeholder="Resultado Z/Y">
                      <button class="btn btn-success copy-btn" type="button" onclick="copyToClipboard('resultCombined', this)" style="width: 130px;" data-label-text="Copiar Z/Y">Copiar Z/Y</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="accordion-item">
              <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseHelper" aria-expanded="false" aria-controls="collapseHelper" id="labelIndividualAccordion">
                  Componentes del Elemento General tipo Serie
                </button>
              </h2>
              <div id="collapseHelper" class="accordion-collapse collapse" data-bs-parent="#componentHelperAccordion">
                <div class="accordion-body component-helper">
                  <label id="labelR" class="form-label small">Resistor (R) / Conductancia (G)</label>
                  <div class="input-group input-group-sm">
                    <input type="text" class="form-control" placeholder="Valor (ej. 10 o 1/15)" id="valR">
                    <span class="input-group-text unit-select" id="labelR_ind_unit">Ω</span>
                    <input type="text" readonly class="form-control form-control-plaintext" id="resultR">
                    <button class="btn btn-outline-secondary copy-btn" type="button" onclick="copyToClipboard('resultR', this)" data-label-text="Copiar Z/Y">Copiar Z/Y</button>
                  </div>
                  
                  <label id="labelL" class="form-label small mt-2">Inductor (L) / Invertancia (Γ)</label>
                  <div class="input-group input-group-sm">
                    <input type="text" class="form-control" placeholder="Valor" id="valL">
                    <select class="form-select unit-select" id="unitL">
                        <option value="1/L">H</option>
                        <option value="1e-3/L" selected>mH</option>
                        <option value="1e-6/L">µH</option>
                        <option value="1/G">H⁻¹</option>
                        <option value="1e-3/G">mH⁻¹</option>
                        <option value="1e3/G">kH⁻¹</option>
                    </select>
                    <input type="text" readonly class="form-control form-control-plaintext" id="resultL">
                    <button class="btn btn-outline-secondary copy-btn" type="button" onclick="copyToClipboard('resultL', this)" data-label-text="Copiar Z/Y">Copiar Z/Y</button>
                  </div>
                  
                  <label id="labelC" class="form-label small mt-2">Capacitor (C) / Daraf (D)</label>
                  <div class="input-group input-group-sm">
                    <input type="text" class="form-control" placeholder="Valor (ej. 100 o 1/60)" id="valC">
                    <select class="form-select unit-select" id="unitC">
                        <option value="1/C">F</option>
                        <option value="1e-3/C">mF</option>
                        <option value="1e-6/C" selected>µF</option>
                        <option value="1e-9/C">nF</option>
                        <option value="1e-12/C">pF</option>
                        <option value="1/D">D</option>
                        <option value="1e-3/D">mD</option>
                        <option value="1e3/D">kD</option>
                    </select>
                    <input type="text" readonly class="form-control form-control-plaintext" id="resultC">
                    <button class="btn btn-outline-secondary copy-btn" type="button" onclick="copyToClipboard('resultC', this)" data-label-text="Copiar Z/Y">Copiar Z/Y</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <p class="small-note">Introduzca valores (ej: 3+0.58j, -1.5j, 120∠0, 1/15). Máx: {{max_size}}x{{max_size}}</p>
          
          <div class="controls row g-3 align-items-md-center">
            <div class="col-auto">
              <label class="form-label mb-0">Tamaño (n x n)</label>
              <input id="nSize" class="form-control" type="number" value="{{default_size}}" min="1" max="{{max_size}}" style="width:110px;">
            </div>
            <div class="col-auto">
              <label class="form-label mb-0">Método</label>
              <select id="methodSelect" class="form-select">
                <option value="auto">Auto</option>
                <option value="cramer">Cramer</option>
                <option value="gauss">Gauss</option>
              </select>
            </div>
            <div class="col-auto pt-4">
              <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" id="autoSolveSwitch" checked>
                <label class="form-check-label" for="autoSolveSwitch">AutoSolve</label>
              </div>
            </div>
            <div class="col-12 col-md-auto pt-4 d-flex flex-wrap gap-2">
              <button id="genBtn" class="btn btn-primary">Generar</button>
              <button id="solveBtn" class="btn btn-success">Resolver</button>
              <button id="pdfBtn" class="btn btn-outline-secondary">Exportar PDF</button>
              
              <button type="button" class="btn btn-outline-info" data-bs-toggle="modal" data-bs-target="#helpModal">
                Ayuda
              </button>
            </div>
            <div class="col-12 col-md-auto ms-auto text-md-end">
              <label class="form-label mb-0">Ejemplos</label><br>
              <div class="btn-group" role="group">
                <button class="btn btn-sm btn-info" onclick="loadExample('rlc')">RLC</button>
                <button class="btn btn-sm btn-info" onclick="loadExample('ac')">AC</button>
                <button class="btn btn-sm btn-info" onclick="loadExample('trif')">Trifásico</button>
              </div>
            </div>
          </div>
          
          <form id="matrixForm" class="mt-3">
            <div class="row g-3">
              <div class="col-lg-8" id="matrixA_col">
                </div>
              <div class="col-lg-4" id="matrixB_col">
                </div>
            </div>
          </form>
          
          <hr class="my-4">
          
          <div class="row g-4">
            <div class="col-lg-7">
              <h5 id="labelResultados">Resultados (Corrientes)</h5>
              
              <div id="resultsArea" class="row g-3">
                  <div class="col-md-6">
                      <h6>Forma Rectangular</h6>
                      <pre id="resultsRect" class="results-box">...</pre>
                  </div>
                  <div class="col-md-6">
                      <h6>Forma Polar</h6>
                      <pre id="resultsPolar" class="results-box">...</pre>
                  </div>
              </div>
              
              <div class="accordion mt-3" id="verificationAccordion">
                <div class="accordion-item" style="border-radius: 12px;">
                  <h2 class="accordion-header">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseVerification" aria-expanded="false" aria-controls="collapseVerification">
                      Verificación de Cálculo (A·x)
                    </button>
                  </h2>
                  <div id="collapseVerification" class="accordion-collapse collapse" data-bs-parent="#verificationAccordion">
                    <div class="accordion-body">
                      <div id="verificationArea" class="row g-3">
                          <div class="col-md-6">
                              <h6>Forma Rectangular</h6>
                              <pre id="verifRect" class="results-box">...</pre>
                          </div>
                          <div class="col-md-6">
                              <h6>Forma Polar</h6>
                              <pre id="verifPolar" class="results-box">...</pre>
                          </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              
            </div>
            <div class="col-lg-5">
              <h5 id="labelFasor">Diagrama fasorial (Corrientes)</h5>
              <div id="fasorArea" class="text-center">
                <a href="#" data-bs-toggle="modal" data-bs-target="#fasorModal">
                  <img id="fasorImg" class="fasor-img" src="/fasor.png?ts=0" alt="Fasor">
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
      <p class="text-muted mt-3 small text-center">CircuitSolve · Creado por Iván</p>
    </div>
    
    
    <div class="modal fade" id="helpModal" tabindex="-1" aria-labelledby="helpModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content" style="border-radius: 20px;">
          <div class="modal-header" style="border-bottom: 1px solid #e0e0e0;">
            <h5 class="modal-title" id="helpModalLabel">Ayuda - CircuitSolve</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body" style="padding: 1.5rem;">
            
            <h6>Modo de Análisis</h6>
            <p>Selecciona el método que estás utilizando:</p>
            <ul class="help-list">
              <li><b>Mallas (Impedancias):</b> La herramienta resolverá <code>[Z][I] = [V]</code>.
                <ul>
                  <li><b>Matriz A:</b> Debe contener Impedancias (Ω).</li>
                  <li><b>Vector b:</b> Debe contener Fuentes de Voltaje (V).</li>
                  <li><b>Resultados:</b> Serán las Corrientes (A) de malla.</li>
                </ul>
              </li>
              <li><b>Nodos (Admitancias):</b> La herramienta resolverá <code>[Y][V] = [I]</code>.
                <ul>
                  <li><b>Matriz A:</b> Debe contener Admitancias (S).</li>
                  <li><b>Vector b:</b> Debe contener Fuentes de Corriente (A).</li>
                  <li><b>Resultados:</b> Serán los Voltajes (V) de nodo.</li>
                </ul>
              </li>
            </ul>
            <hr>
            <h6>Formatos Aceptados</h6>
            <p>Puedes usar los siguientes formatos en cualquier celda:</p>
            <ul class="help-list">
              <li><b>Rectangular:</b> <code>10+5j</code>, <code>-2.5j</code>, <code>15</code></li>
              <li><b>Polar:</b> <code>120∠-30</code> (el símbolo <code>°</code> es opcional)</li>
              <li><b>Fracciones:</b> <code>1/15</code>, <code>-3/4</code> (solo para valores reales como R o G)</li>
            </ul>
            <hr>
            <h6>Ayudante de Componentes</h6>
            <p>El ayudante calcula el valor complejo correcto (Z o Y) basado en el modo de análisis seleccionado.</p>
            <ul class="help-list">
              <li><b>R/G:</b> Introduce Resistencia (R) en <code>Ω</code> (Mallas) o Conductancia (G) en <code>S</code> (Nodos).</li>
              <li><b>L/Γ y C/D:</b> La calculadora es "dual". Puedes introducir el valor normal (L en Henries, C en Farads) o su valor inverso (Γ en H⁻¹, D en Darafs). El programa usará la fórmula correcta automáticamente basado en la unidad que selecciones.</li>
            </ul>
          </div>
          <div class="modal-footer" style="border-top: 1px solid #e0e0e0;">
            <button type="button" class="btn btn-primary" data-bs-dismiss="modal">Entendido</button>
          </div>
        </div>
      </div>
    </div>
    
    <div class="modal fade" id="fasorModal" tabindex="-1" aria-labelledby="fasorModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content" style="background-color: transparent; border: none;">
          <div class="modal-body text-center p-0">
            <img id="modalFasorImg" src="/fasor.png?ts=0" class="img-fluid" alt="Diagrama Fasorial" style="border-radius: 12px; background: #fff;">
          </div>
        </div>
      </div>
    </div>
    <script>
      const maxSize = {{max_size}};
      let debounceTimer = null;
      const debounceDelay = 700;
      let currentMode = 'mallas';

      function parseJSValue(str) {
          str = String(str).trim();
          if (str === "") return 0;
          if (str.includes('/')) {
              const parts = str.split('/');
              if (parts.length === 2) {
                  const num = parseFloat(parts[0]);
                  const den = parseFloat(parts[1]);
                  if (!isNaN(num) && !isNaN(den) && den !== 0) {
                      return num / den;
                  }
              }
          }
          const val = parseFloat(str);
          return isNaN(val) ? 0 : val;
      }

      function formatComplexJS(real, imag, precision = 6) {
          const r = parseFloat(real.toFixed(precision));
          const i = parseFloat(imag.toFixed(precision));
          if (Math.abs(i) < 1e-12) return r.toString();
          if (Math.abs(r) < 1e-12) return (i > 0 ? '+' : '') + i.toString() + 'j';
          const sign = i > 0 ? '+' : '-';
          return r.toString() + ' ' + sign + ' ' + Math.abs(i).toString() + 'j';
      }

      function copyToClipboard(elementId, buttonElement) {
          const textToCopy = document.getElementById(elementId).value;
          if (!textToCopy) return;
          
          const originalText = buttonElement.dataset.labelText || buttonElement.textContent;
          
          if (navigator.clipboard) {
              navigator.clipboard.writeText(textToCopy).then(() => {
                  buttonElement.textContent = '¡Copiado!';
                  setTimeout(() => {
                      buttonElement.textContent = originalText;
                  }, 1500);
              }).catch(err => console.error('Error al copiar: ', err));
          }
      }

      function getUnitParts(unitString) {
          const parts = unitString.split('/');
          return {
              multiplier: parseFloat(parts[0]),
              type: parts[1] // 'L', 'G' (Gamma), 'C', 'D'
          };
      }

      function calculateCombined() {
          try {
              const freqVal = parseJSValue(document.getElementById('freqInput').value);
              const freqType = document.getElementById('freqType').value;
              if (freqVal <= 0) {
                  document.getElementById('resultCombined').value = "Freq > 0";
                  return;
              }
              const omega = (freqType === 'hz') ? (2 * Math.PI * freqVal) : freqVal;
              
              const R_G_val = parseJSValue(document.getElementById('valR_comb').value);
              
              const L_unit_parts = getUnitParts(document.getElementById('unitL_comb').value);
              const L_val = parseJSValue(document.getElementById('valL_comb').value) * L_unit_parts.multiplier;
              const L_type = L_unit_parts.type;

              const C_unit_parts = getUnitParts(document.getElementById('unitC_comb').value);
              const C_val = parseJSValue(document.getElementById('valC_comb').value) * C_unit_parts.multiplier;
              const C_type = C_unit_parts.type;

              let real = 0.0, imag = 0.0;
              let imag_L = 0.0, imag_C = 0.0;
              
              if (currentMode === 'mallas') {
                  // Z = R + Z_L + Z_C
                  real = R_G_val; // Z_R = R
                  if (omega > 0 && L_val > 0) {
                      if (L_type === 'L') { imag_L = omega * L_val; } // Z = jωL
                      else { imag_L = omega / L_val; } // Z = jω/Γ (Invertancia)
                  }
                  if (omega > 0 && C_val > 0) {
                      if (C_type === 'C') { imag_C = -1 / (omega * C_val); } // Z = -j/(ωC)
                      else { imag_C = -C_val / omega; } // Z = -jD/ω (Daraf)
                  }
                  imag = imag_L + imag_C;
              } else {
                  // Y = G + Y_L + Y_C
                  real = R_G_val; // Y_R = G
                  if (omega > 0 && L_val > 0) {
                      if (L_type === 'L') { imag_L = -1 / (omega * L_val); } // Y = -j/(ωL)
                      else { imag_L = -L_val / omega; } // Y = -jΓ/ω (Invertancia)
                  }
                  if (omega > 0 && C_val > 0) {
                      if (C_type === 'C') { imag_C = omega * C_val; } // Y = jωC
                      else { imag_C = omega / C_val; } // Y = jω/D (Daraf)
                  }
                  imag = imag_L + imag_C;
              }
              
              document.getElementById('resultCombined').value = formatComplexJS(real, imag, 8);
          } catch (e) {
              console.error("Error al calcular Z/Y combinada: ", e);
              document.getElementById('resultCombined').value = "Error";
          }
      }
      
      function calculateComponent(type) {
          try {
              const freqVal = parseJSValue(document.getElementById('freqInput').value);
              const freqType = document.getElementById('freqType').value;
              
              if (freqVal <= 0) {
                  if (type === 'R') document.getElementById('resultR').value = "Freq > 0";
                  if (type === 'L') document.getElementById('resultL').value = "Freq > 0";
                  if (type === 'C') document.getElementById('resultC').value = "Freq > 0";
                  return;
              }
              
              const omega = (freqType === 'hz') ? (2 * Math.PI * freqVal) : freqVal;
              let real = 0.0, imag = 0.0, val;

              if (type === 'R') {
                  val = parseJSValue(document.getElementById('valR').value);
                  real = val; // Z_R = R  ó  Y_R = G.
                  document.getElementById('resultR').value = formatComplexJS(real, imag);

              } else if (type === 'L') {
                  const unit_parts = getUnitParts(document.getElementById('unitL').value);
                  val = parseJSValue(document.getElementById('valL').value) * unit_parts.multiplier;
                  
                  if (omega > 0 && val > 0) {
                      if (currentMode === 'mallas') {
                          if (unit_parts.type === 'L') { imag = omega * val; } // Z = jωL
                          else { imag = omega / val; } // Z = jω/Γ
                      } else {
                          if (unit_parts.type === 'L') { imag = -1 / (omega * val); } // Y = -j/(ωL)
                          else { imag = -val / omega; } // Y = -jΓ/ω
                      }
                  }
                  document.getElementById('resultL').value = formatComplexJS(real, imag);

              } else if (type === 'C') {
                  const unit_parts = getUnitParts(document.getElementById('unitC').value);
                  val = parseJSValue(document.getElementById('valC').value) * unit_parts.multiplier;

                  if (omega > 0 && val > 0) {
                      if (currentMode === 'mallas') {
                          if (unit_parts.type === 'C') { imag = -1 / (omega * val); } // Z = -j/(ωC)
                          else { imag = -val / omega; } // Z = -jD/ω
                      } else {
                          if (unit_parts.type === 'C') { imag = omega * val; } // Y = jωC
                          else { imag = omega / val; } // Y = jω/D
                      }
                  }
                  document.getElementById('resultC').value = formatComplexJS(real, imag);
              }
          } catch(e) {
              console.error("Error al calcular componente: ", e);
          }
      }
      
      document.addEventListener('DOMContentLoaded', () => {
          // ... (Sin cambios) ...
          document.getElementById('valR').addEventListener('input', () => calculateComponent('R'));
          document.getElementById('valL').addEventListener('input', () => calculateComponent('L'));
          document.getElementById('unitL').addEventListener('change', () => calculateComponent('L'));
          document.getElementById('valC').addEventListener('input', () => calculateComponent('C'));
          document.getElementById('unitC').addEventListener('change', () => calculateComponent('C'));
          document.getElementById('valR_comb').addEventListener('input', calculateCombined);
          document.getElementById('valL_comb').addEventListener('input', calculateCombined);
          document.getElementById('unitL_comb').addEventListener('change', calculateCombined);
          document.getElementById('valC_comb').addEventListener('input', calculateCombined);
          document.getElementById('unitC_comb').addEventListener('change', calculateCombined);
          const freqInputs = ['freqInput', 'freqType'];
          freqInputs.forEach(id => {
              const el = document.getElementById(id);
              el.addEventListener('input', () => {
                  calculateComponent('R');
                  calculateComponent('L');
                  calculateComponent('C');
                  calculateCombined();
              });
              el.addEventListener('change', () => {
                  calculateComponent('R');
                  calculateComponent('L');
                  calculateComponent('C');
                  calculateCombined();
              });
          });
          
          setMode(currentMode);
      });
      
      function setMode(mode) {
        currentMode = mode;
        const btnMallas = document.getElementById('btnMallas');
        const btnNodos = document.getElementById('btnNodos');
        
        // Limpiar campos del ayudante
        const helperInputs = ['valR_comb', 'valL_comb', 'valC_comb', 'valR', 'valL', 'valC'];
        helperInputs.forEach(id => {
            document.getElementById(id).value = '';
        });
        
        const labels = {
            mallas: {
                matrizA: "Matriz A (Impedancias)",
                vectorB: "Vector b (Fuentes de Voltaje)",
                vectorB_pref: "V",
                resultados: "Resultados (Corrientes)",
                fasor: "Diagrama fasorial (Corrientes)",
                labelR: "Resistor (R)",
                comb_R_text: "R",
                comb_R_unit: "Ω",
                ind_R_unit: "Ω",
                accordionCombined: "Elemento General tipo Serie",
                accordionIndividual: "Componentes del Elemento General tipo Serie",
                combinedBoxLabel: "Componentes en Serie",
                copyBtnLabel: "Copiar Z"
            },
            nodos: {
                matrizA: "Matriz A (Admitancias)",
                vectorB: "Vector b (Fuentes de Corriente)",
                vectorB_pref: "I",
                resultados: "Resultados (Voltajes de Nodo)",
                fasor: "Diagrama fasorial (Voltajes)",
                labelR: "Conductancia (G)",
                comb_R_text: "G",
                comb_R_unit: "S",
                ind_R_unit: "S",
                accordionCombined: "Elemento General tipo Paralelo",
                accordionIndividual: "Componentes del Elemento General tipo Paralelo",
                combinedBoxLabel: "Componentes en Paralelo",
                copyBtnLabel: "Copiar Y"
            }
        };
        
        const modeLabels = labels[mode];

        document.getElementById('labelMatrizA').textContent = modeLabels.matrizA;
        document.getElementById('labelVectorB').textContent = modeLabels.vectorB;
        document.getElementById('labelResultados').textContent = modeLabels.resultados;
        document.getElementById('labelFasor').textContent = modeLabels.fasor;
        document.getElementById('labelR').textContent = modeLabels.labelR;
        document.getElementById('labelR_comb_text').textContent = modeLabels.comb_R_text;
        document.getElementById('labelR_comb_unit').textContent = modeLabels.comb_R_unit;
        document.getElementById('labelR_ind_unit').textContent = modeLabels.ind_R_unit;
        document.getElementById('labelL').textContent = "Inductor (L) / Invertancia (Γ)";
        document.getElementById('labelC').textContent = "Capacitor (C) / Daraf (D)";
        document.getElementById('labelL_comb_text').textContent = "L/Γ";
        document.getElementById('labelC_comb_text').textContent = "C/D";
        
        document.getElementById('labelCombinedAccordion').textContent = modeLabels.accordionCombined;
        document.getElementById('labelIndividualAccordion').textContent = modeLabels.accordionIndividual;
        document.getElementById('labelCombinedBox').textContent = modeLabels.combinedBoxLabel;

        // Actualizar etiquetas de botones "Copiar"
        document.querySelectorAll('.copy-btn').forEach(btn => {
            btn.textContent = modeLabels.copyBtnLabel;
            btn.dataset.labelText = modeLabels.copyBtnLabel;
        });

        const b_inputs = document.querySelectorAll('[name^="b_"]');
        b_inputs.forEach(function(inp) {
            const labelCell = inp.closest('tr').querySelector('td:first-child');
            if (labelCell) {
                const index = labelCell.textContent.replace (/[^0-9]/g, '');
                labelCell.textContent = modeLabels.vectorB_pref + index;
            }
        });

        if (mode === 'mallas') {
            btnMallas.classList.add('active', 'btn-primary');
            btnMallas.classList.remove('btn-outline-primary');
            btnNodos.classList.remove('active', 'btn-primary');
            btnNodos.classList.add('btn-outline-primary');
        } else {
            btnNodos.classList.add('active', 'btn-primary');
            btnNodos.classList.remove('btn-outline-primary');
            btnMallas.classList.remove('active', 'btn-primary');
            btnMallas.classList.add('btn-outline-primary');
        }
        
        calculateComponent('R');
        calculateComponent('L');
        calculateComponent('C');
        calculateCombined();
        
        if (document.getElementById('autoSolveSwitch').checked) {
            doSolve(false);
        }
      }

      function makeMatrix(n) {
        const contA = document.getElementById('matrixA_col');
        const contB = document.getElementById('matrixB_col');
        contA.innerHTML = '';
        contB.innerHTML = '';
        
        let htmlA = '';
        htmlA += '<div class="mb-2"><label id="labelMatrizA" class="form-label">Matriz A (Impedancias)</label>';
        htmlA += '<div class="table-responsive-wrapper">';
        htmlA += '<table class="table table-bordered table-striped table-hover"><tbody>';
        for (let i=0;i<n;i++){
          htmlA += '<tr>';
          for (let j=0;j<n;j++){
            htmlA += '<td><input class="form-control matrix-input" name="A_' + i + '_' + j + '" value="0"></td>';
          }
          htmlA += '</tr>';
        }
        htmlA += '</tbody></table></div></div>'; 
        
        let htmlB = '';
        htmlB += '<div class="mb-2"><label id="labelVectorB" class="form-label">Vector b (Fuentes de Voltaje)</label>';
        htmlB += '<div class="table-responsive-wrapper">';
        htmlB += '<table class="table table-bordered table-striped"><tbody>';
        
        for (let i=0; i<n; i++){
          htmlB += '<tr><td>V' + (i+1) + '</td><td><input class="form-control matrix-input" name="b_' + i + '" value="0"></td></tr>';
        }
        
        htmlB += '</tbody></table></div></div>';
        
        contA.innerHTML = htmlA;
        contB.innerHTML = htmlB;
        
        setInputChangeHandlers();
        setMode(currentMode);
      }

      function setInputChangeHandlers() {
        const inputs = document.querySelectorAll('#matrixForm input');
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
        return {matrix: A, vector: b, method: document.getElementById('methodSelect').value, mode: currentMode};
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

      /*** ### FASE 3.7 - MODIFICADO ### Formato de Resultados y Verificación a Pestañas ***/
      async function doSolve(downloadPdf) {
        if (downloadPdf === undefined) { downloadPdf = false; }
        const payload = collectForm();
        
        // Contenedores de pestañas
        const outRect = document.getElementById('resultsRect');
        const outPolar = document.getElementById('resultsPolar');
        const verifRect = document.getElementById('verifRect');
        const verifPolar = document.getElementById('verifPolar');
        
        try {
            const res = await fetch('/solve', {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify(payload)
            });
            if (!res.ok) {
              const err = await res.json();
              const errorMsg = "ERROR: " + (err.error || JSON.stringify(err));
              outRect.textContent = errorMsg;
              outPolar.textContent = errorMsg;
              verifRect.textContent = "ERROR";
              verifPolar.textContent = "ERROR";
              return;
            }
            const data = await res.json();
            
            const resultPrefix = currentMode === 'mallas' ? 'I' : 'V';
            const unit = currentMode === 'mallas' ? 'A' : 'V';
            const verificationPrefix = currentMode === 'mallas' ? 'Malla' : 'Nodo';

            // Formatear Resultados Principales
            let s_results_rect = "";
            let s_results_polar = "";
            data.result.forEach(function(el, idx) {
              let name = (resultPrefix + (idx+1)).padEnd(4, ' ');
              s_results_rect += `${name}= ${el.rect} ${unit}\n`;
              s_results_polar += `${name}= |${resultPrefix}|=${el.mag.toFixed(4)} ${unit}  ∠ ${el.angle.toFixed(4)}°\n`;
            });
            outRect.textContent = s_results_rect;
            outPolar.textContent = s_results_polar;
            
            // Formatear Verificación
            let s_verif_rect = "";
            let s_verif_polar = "";
            data.vcalc.forEach(function(el, i) {
              let name = (verificationPrefix + ' ' + (i+1)).padEnd(8, ' ');
              s_verif_rect += `${name}: ${el.rect}\n`;
              s_verif_polar += `${name}: ${el.mag.toFixed(4)} ∠ ${el.angle.toFixed(4)}°\n`;
            });
            verifRect.textContent = s_verif_rect;
            verifPolar.textContent = s_verif_polar;

            // Actualizar imágenes
            const img = document.getElementById('fasorImg');
            const modalImg = document.getElementById('modalFasorImg');
            const newSrc = '/fasor.png?ts=' + Date.now();
            img.src = newSrc;
            modalImg.src = newSrc;
            
            if (downloadPdf) {
              /*** ### FASE 3.7 - CORRECCIÓN DE BUG (ts='D) ### ***/
              window.location.href = '/download_pdf?ts=' + Date.now();
            }
        } catch (e) {
            const errorMsg = "ERROR de conexión: " + e.message;
            outRect.textContent = errorMsg;
            outPolar.textContent = errorMsg;
            verifRect.textContent = errorMsg;
            verifPolar.textContent = errorMsg;
        }
      }

      // ... (Botones sin cambios) ...
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
        calculateComponent('R');
        calculateComponent('L');
        calculateComponent('C');
        calculateCombined();
      });
    </script>
  </body>
</html>
"""

# 11. Endpoints (Rutas) de la API de Flask
LAST = {"A_strings": None, "b_strings": None, "x": None, "fasor_bytes": None, "A_numpy": None, "b_numpy": None, "mode": "mallas"}

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

 ### FASE 3.7 - MODIFICADO ### Precisión 4 decimales ***/
@app.route('/solve', methods=['POST'])
def solve_route():
    try:
        data = request.get_json()
        A_strings = data.get('matrix')
        b_strings = data.get('vector')
        method = data.get('method', 'auto')
        mode = data.get('mode', 'mallas')
        
        A, b = validate_and_build_A_b(A_strings, b_strings)
        x = solve_system(A, b, method=method)
        
        pretty_results = []
        for xi in x:
            rect = format_rect(xi, precision=4) # Precisión de 4 decimales
            mag, ang = rect_to_polar(xi)
            pretty_results.append({"rect": rect, "mag": mag, "angle": ang})
        
        Vcalc = (A @ x).tolist()
        
        # Crear lista estructurada para la verificación
        Vcalc_pretty = []
        for v in Vcalc:
            rect = format_rect(v, precision=4) # Precisión de 4 decimales
            mag, ang = rect_to_polar(v)
            Vcalc_pretty.append({"rect": rect, "mag": mag, "angle": ang})
        
        fasor_buf = make_fasor_png(x, mode=mode)
        
        LAST['A_strings'] = A_strings
        LAST['b_strings'] = b_strings
        LAST['x'] = x
        LAST['fasor_bytes'] = fasor_buf.getvalue()
        LAST['A_numpy'] = A
        LAST['b_numpy'] = b
        LAST['mode'] = mode
        
        return jsonify({"result": pretty_results, "vcalc": Vcalc_pretty})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/fasor.png')
def fasor_png():
    mode = LAST.get('mode', 'mallas')
    if LAST.get('fasor_bytes') is None:
        buf = make_fasor_png(np.array([]), mode=mode)
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
            LAST['b_numpy'],
            LAST.get('mode', 'mallas')
        )
        return send_file(
            pdf_bytes_io, 
            mimetype='application/pdf', 
            as_attachment=True, 
            download_name='CircuitSolve_Reporte.pdf'
        )
    except Exception as e:
        return f"Error generando PDF: {e}", 500

# 12. Punto de Entrada Principal
if __name__ == "__main__":
    print("================================================================")
    print("Iniciando CircuitSolve (Fase 3.7 - Final)")
    print(f"Servidor corriendo en http://127.0.0.1:5000 y en tu IP local.")
    print("Presiona CTRL+C para detener.")
    print("================================================================")
    app.run(debug=True, port=5000, use_reloader=True, host='0.0.0.0')
