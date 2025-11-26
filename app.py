from flask import Flask, render_template, request, jsonify, send_file
import json
import os
import sqlite3
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import requests
import base64

app = Flask(__name__)
app.secret_key = 'clave_secreta_2024'

DB_FILE = 'participantes.db'
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = os.environ.get('REPO_OWNER', 'tu_usuario')  # Cambia por tu usuario de GitHub
REPO_NAME = os.environ.get('REPO_NAME', 'tu_repositorio')  # Cambia por el nombre de tu repo

def init_db():
    """Inicializar la base de datos local"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS participantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telefono TEXT NOT NULL,
            genero TEXT NOT NULL,
            empresa TEXT,
            comentarios TEXT,
            fecha_inscripcion TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def descargar_db_desde_github():
    """Descargar la base de datos desde GitHub al iniciar"""
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN no configurado - usando base de datos local")
        return
    
    try:
        url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DB_FILE}'
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = response.json()['content']
            # Decodificar contenido base64
            db_content = base64.b64decode(content)
            with open(DB_FILE, 'wb') as f:
                f.write(db_content)
            print("✅ Base de datos descargada desde GitHub")
        else:
            print(f"⚠️  No se encontró BD en GitHub: {response.status_code}")
    except Exception as e:
        print(f"⚠️  No se pudo descargar la BD: {e}")

def subir_db_a_github():
    """Subir la base de datos actualizada a GitHub"""
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN no configurado - no se puede subir a GitHub")
        return
    
    try:
        # Verificar si el archivo existe
        if not os.path.exists(DB_FILE):
            print("⚠️  No existe archivo de BD para subir")
            return
        
        # Leer archivo local
        with open(DB_FILE, 'rb') as f:
            content = f.read()
        
        # Codificar en base64
        encoded_content = base64.b64encode(content).decode('utf-8')
        
        # Obtener SHA del archivo actual (si existe)
        url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DB_FILE}'
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        
        sha = None
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            sha = response.json()['sha']
        
        # Subir archivo
        data = {
            'message': f'Actualización BD - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'content': encoded_content,
            'sha': sha
        }
        
        response = requests.put(url, headers=headers, json=data)
        if response.status_code in [200, 201]:
            print("✅ Base de datos subida a GitHub")
        else:
            print(f"❌ Error al subir: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error subiendo a GitHub: {e}")

def get_db_connection():
    """Obtener conexión a la base de datos"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_first_request
def startup():
    """Ejecutar al iniciar la aplicación"""
    print("🚀 Iniciando aplicación...")
    init_db()
    descargar_db_desde_github()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/guardar', methods=['POST'])
def guardar_participante():
    try:
        data = request.json
        conn = get_db_connection()
        
        # Verificar duplicado
        existing = conn.execute(
            'SELECT id FROM participantes WHERE email = ?', 
            (data['email'].lower(),)
        ).fetchone()
        
        if existing:
            conn.close()
            return jsonify({'error': 'Email ya registrado'}), 400
        
        # Insertar nuevo participante
        fecha_actual = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        timestamp_actual = datetime.now().isoformat()
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO participantes 
            (nombre, email, telefono, genero, empresa, comentarios, fecha_inscripcion, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['nombre'],
            data['email'].lower(),
            data['telefono'],
            data['genero'],
            data.get('empresa', ''),
            data.get('comentarios', ''),
            fecha_actual,
            timestamp_actual
        ))
        
        participante_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Subir cambios a GitHub
        subir_db_a_github()
        
        return jsonify({
            'success': True, 
            'message': 'Registro exitoso',
            'id': participante_id
        })
        
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

@app.route('/obtener', methods=['GET'])
def obtener_participantes():
    try:
        conn = get_db_connection()
        participantes = conn.execute('SELECT * FROM participantes ORDER BY id DESC').fetchall()
        conn.close()
        
        # Convertir a lista de diccionarios en el formato que espera el frontend
        participantes_list = []
        for p in participantes:
            participantes_list.append({
                'id': p['id'],
                'nombre': p['nombre'],
                'email': p['email'],
                'telefono': p['telefono'],
                'genero': p['genero'],
                'empresa': p['empresa'] or '',
                'comentarios': p['comentarios'] or '',
                'fechaInscripcion': p['fecha_inscripcion'],
                'timestamp': p['timestamp']
            })
        
        return jsonify(participantes_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generar-excel', methods=['GET'])
def generar_excel():
    try:
        conn = get_db_connection()
        participantes = conn.execute('SELECT * FROM participantes ORDER BY id DESC').fetchall()
        conn.close()
        
        if not participantes:
            return jsonify({'error': 'No hay datos para exportar'}), 400
        
        # Crear Excel con openpyxl
        wb = Workbook()
        ws = wb.active
        ws.title = "Participantes"
        
        # Encabezados
        headers = ['ID', 'Nombre', 'Email', 'Teléfono', 'Género', 'Empresa', 'Comentarios', 'Fecha de Inscripción']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Datos
        for row, participante in enumerate(participantes, 2):
            ws.cell(row=row, column=1, value=participante['id'])
            ws.cell(row=row, column=2, value=participante['nombre'])
            ws.cell(row=row, column=3, value=participante['email'])
            ws.cell(row=row, column=4, value=participante['telefono'])
            ws.cell(row=row, column=5, value=participante['genero'])
            ws.cell(row=row, column=6, value=participante['empresa'] or '')
            ws.cell(row=row, column=7, value=participante['comentarios'] or '')
            ws.cell(row=row, column=8, value=participante['fecha_inscripcion'])
        
        # Ajustar anchos de columna
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)  # Máximo 50 caracteres
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Guardar en memoria
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'participantes_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/eliminar-todos', methods=['POST'])
def eliminar_todos():
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM participantes')
        conn.commit()
        conn.close()
        
        # Subir cambios a GitHub (base de datos vacía)
        subir_db_a_github()
        
        return jsonify({'success': True, 'message': 'Todos los datos eliminados'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para verificar el estado de la base de datos
@app.route('/estado', methods=['GET'])
def estado_db():
    try:
        conn = get_db_connection()
        count = conn.execute('SELECT COUNT(*) as total FROM participantes').fetchone()['total']
        conn.close()
        
        return jsonify({
            'estado': 'ok',
            'total_participantes': count,
            'bd_existe': os.path.exists(DB_FILE),
            'github_token_configurado': bool(GITHUB_TOKEN)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Inicializar base de datos al iniciar
    init_db()
    descargar_db_desde_github()
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
