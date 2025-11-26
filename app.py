from flask import Flask, render_template, request, jsonify, send_file
import json
import os
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

app = Flask(__name__)
app.secret_key = 'clave_secreta_2024'

DB_FILE = 'participantes.json'

def cargar_participantes():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_participantes(participantes):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(participantes, f, ensure_ascii=False, indent=2)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/guardar', methods=['POST'])
def guardar_participante():
    try:
        data = request.json
        participantes = cargar_participantes()
        
        # Verificar duplicado
        if any(p['email'].lower() == data['email'].lower() for p in participantes):
            return jsonify({'error': 'Email ya registrado'}), 400
        
        nuevo = {
            'id': len(participantes) + 1,
            'nombre': data['nombre'],
            'email': data['email'],
            'telefono': data['telefono'],
            'genero': data['genero'],
            'empresa': data.get('empresa', ''),
            'comentarios': data.get('comentarios', ''),
            'fechaInscripcion': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
            'timestamp': datetime.now().isoformat()
        }
        
        participantes.append(nuevo)
        guardar_participantes(participantes)
        
        return jsonify({
            'success': True, 
            'message': 'Registro exitoso',
            'id': nuevo['id']
        })
        
    except Exception as e:
        return jsonify({'error': f'Error del servidor: {str(e)}'}), 500

@app.route('/obtener', methods=['GET'])
def obtener_participantes():
    try:
        participantes = cargar_participantes()
        return jsonify(participantes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generar-excel', methods=['GET'])
def generar_excel():
    try:
        participantes = cargar_participantes()
        
        if not participantes:
            return jsonify({'error': 'No hay datos para exportar'}), 400
        
        # Crear Excel con openpyxl (sin pandas)
        wb = Workbook()
        ws = wb.active
        ws.title = "Participantes"
        
        # Encabezados
        headers = ['Nombre', 'Email', 'Teléfono', 'Género', 'Empresa', 'Comentarios', 'Fecha de Inscripción']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
        
        # Datos
        for row, participante in enumerate(participantes, 2):
            ws.cell(row=row, column=1, value=participante['nombre'])
            ws.cell(row=row, column=2, value=participante['email'])
            ws.cell(row=row, column=3, value=participante['telefono'])
            ws.cell(row=row, column=4, value=participante['genero'])
            ws.cell(row=row, column=5, value=participante.get('empresa', ''))
            ws.cell(row=row, column=6, value=participante.get('comentarios', ''))
            ws.cell(row=row, column=7, value=participante['fechaInscripcion'])
        
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
            adjusted_width = (max_length + 2)
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
        guardar_participantes([])
        return jsonify({'success': True, 'message': 'Todos los datos eliminados'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
