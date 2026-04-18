from flask import Flask, render_template, request, redirect, url_for, session, send_file
import csv
import os
import json
from datetime import datetime
from openpyxl import Workbook
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta_femp_2026'


def cargar_usuarios():
    archivo = 'usuarios.json'
    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def obtener_usuario(usuario_ingresado):
    usuarios = cargar_usuarios()
    for usuario in usuarios:
        if usuario.get('usuario') == usuario_ingresado:
            return usuario
    return None


def validar_usuario(usuario_ingresado, clave_ingresada):
    usuario = obtener_usuario(usuario_ingresado)
    if not usuario:
        return False

    clave_db = str(usuario.get('clave', '')).strip()

    if clave_ingresada == clave_db:
        return True

    try:
        if check_password_hash(clave_db, clave_ingresada):
            return True
    except:
        pass

    return False


def obtener_area(curso):
    medicina_tactica = [
        'Medicina Táctica',
        'Manejo de Hemorragias',
        'Manejo de Fracturas',
        'Sutura',
        'Canalización de Paciente',
        'Curso de Manejo de Mina',
        'Concepto y Manejo del Paciente en Aeromedicina',
        'Manejo de Arma de Fuego',
        'Primer respondiente en disturbios públicos'
    ]

    primeros_auxilios = [
        'Primeros Auxilios Básicos',
        'Primeros Auxilios Psicológicos'
    ]

    salud_mental = [
        'Prevención del Suicidio y Autolesión',
        'Intervención en Crisis y Desastres',
        'Atención Psicosocial a Víctimas de Violencia',
        'Prevención del Abuso Sexual Infantil',
        'Cuidado y Prevención del Maltrato Infantil',
        'Salud Mental para Cuidadores'
    ]

    cursos_complementarios = [
        'Básico de Inteligencia',
        'Inteligencia Avanzada',
        'Contrainteligencia',
        'Protección VP',
        'Método de la Investigación Criminalista',
        'Análisis Superior',
        'Derechos Humanos',
        'Detective Privado',
        'Reclutamiento de Fuentes',
        'Perfil Sospechoso'
    ]

    if curso in medicina_tactica:
        return 'Medicina Táctica'
    elif curso in primeros_auxilios:
        return 'Primeros Auxilios'
    elif curso in salud_mental:
        return 'Salud Mental'
    elif curso in cursos_complementarios:
        return 'Cursos Complementarios'
    else:
        return 'Otros'


def convertir_fecha(fecha_texto):
    try:
        return datetime.strptime(fecha_texto, '%d/%m/%Y %H:%M')
    except:
        return None


def es_admin():
    return session.get('rol') == 'admin'


@app.route('/')
def inicio():
    return render_template('index.html')


@app.route('/cursos')
def cursos():
    return render_template('cursos.html')


@app.route('/inscripcion', methods=['GET', 'POST'])
def inscripcion():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        curso = request.form['curso']
        fecha = datetime.now().strftime('%d/%m/%Y %H:%M')

        archivo = 'inscripciones.csv'
        existe = os.path.isfile(archivo)

        with open(archivo, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if not existe:
                writer.writerow(['Nombre', 'Correo', 'Curso', 'Fecha'])

            writer.writerow([nombre, correo, curso, fecha])

        return render_template('gracias.html', nombre=nombre)

    return render_template('inscripcion.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        usuario = request.form['usuario']
        clave = request.form['clave']

        if validar_usuario(usuario, clave):
            usuario_data = obtener_usuario(usuario)
            session['logueado'] = True
            session['usuario'] = usuario
            session['rol'] = usuario_data.get('rol', 'operador')
            return redirect(url_for('inscritos'))
        else:
            error = 'Usuario o contraseña incorrectos'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logueado', None)
    session.pop('usuario', None)
    session.pop('rol', None)
    return redirect(url_for('login'))


@app.route('/inscritos')
def inscritos():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    registros = []
    archivo = 'inscripciones.csv'
    busqueda = request.args.get('q', '').strip().lower()
    area_filtro = request.args.get('area', '').strip()
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()

    fecha_desde_dt = None
    fecha_hasta_dt = None

    try:
        if fecha_desde:
            fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
    except:
        fecha_desde_dt = None

    try:
        if fecha_hasta:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_dt = fecha_hasta_dt.replace(hour=23, minute=59, second=59)
    except:
        fecha_hasta_dt = None

    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)

            for i, fila in enumerate(reader):
                if len(fila) == 4:
                    area = obtener_area(fila[2])
                    fecha_registro_dt = convertir_fecha(fila[3])

                    registro = {
                        'id': i,
                        'nombre': fila[0],
                        'correo': fila[1],
                        'curso': fila[2],
                        'fecha': fila[3],
                        'area': area
                    }

                    texto = f"{fila[0]} {fila[1]} {fila[2]} {fila[3]} {area}".lower()

                    coincide_texto = (not busqueda or busqueda in texto)
                    coincide_area = (not area_filtro or area == area_filtro)

                    coincide_fecha = True
                    if fecha_registro_dt:
                        if fecha_desde_dt and fecha_registro_dt < fecha_desde_dt:
                            coincide_fecha = False
                        if fecha_hasta_dt and fecha_registro_dt > fecha_hasta_dt:
                            coincide_fecha = False

                    if coincide_texto and coincide_area and coincide_fecha:
                        registros.append(registro)

    total_inscritos = len(registros)

    areas_resumen = {}
    for r in registros:
        area = r['area']
        areas_resumen[area] = areas_resumen.get(area, 0) + 1

    ultimo_inscrito = registros[-1] if registros else None

    grafico_labels = list(areas_resumen.keys())
    grafico_valores = list(areas_resumen.values())

    return render_template(
        'inscritos.html',
        registros=registros,
        busqueda=busqueda,
        area_filtro=area_filtro,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        total_inscritos=total_inscritos,
        areas_resumen=areas_resumen,
        ultimo_inscrito=ultimo_inscrito,
        grafico_labels=grafico_labels,
        grafico_valores=grafico_valores,
        usuario_actual=session.get('usuario'),
        rol_actual=session.get('rol'),
        es_admin=es_admin()
    )


@app.route('/descargar-inscritos')
def descargar_inscritos():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    archivo = 'inscripciones.csv'

    if os.path.isfile(archivo):
        return send_file(
            archivo,
            as_attachment=True,
            download_name='inscritos.csv'
        )

    return redirect(url_for('inscritos'))


@app.route('/descargar-excel')
def descargar_excel():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    archivo_csv = 'inscripciones.csv'
    archivo_excel = 'inscritos.xlsx'

    wb = Workbook()
    ws = wb.active
    ws.title = "Inscritos"

    encabezados = ['Nombre', 'Correo', 'Curso', 'Fecha']
    ws.append(encabezados)

    if os.path.isfile(archivo_csv):
        with open(archivo_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)

            for fila in reader:
                if len(fila) == 4:
                    ws.append(fila)

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[column].width = max_length + 4

    wb.save(archivo_excel)

    return send_file(
        archivo_excel,
        as_attachment=True,
        download_name='inscritos.xlsx'
    )


@app.route('/eliminar-inscrito/<int:registro_id>', methods=['POST'])
def eliminar_inscrito(registro_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    archivo = 'inscripciones.csv'
    filas = []

    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            encabezado = next(reader, None)

            for fila in reader:
                if len(fila) == 4:
                    filas.append(fila)

        if 0 <= registro_id < len(filas):
            filas.pop(registro_id)

        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(encabezado if encabezado else ['Nombre', 'Correo', 'Curso', 'Fecha'])
            writer.writerows(filas)

    return redirect(url_for('inscritos'))


@app.route('/editar-inscrito/<int:registro_id>', methods=['GET', 'POST'])
def editar_inscrito(registro_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    archivo = 'inscripciones.csv'
    filas = []
    encabezado = ['Nombre', 'Correo', 'Curso', 'Fecha']

    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            encabezado_archivo = next(reader, None)

            if encabezado_archivo:
                encabezado = encabezado_archivo

            for fila in reader:
                if len(fila) == 4:
                    filas.append(fila)

    if not (0 <= registro_id < len(filas)):
        return redirect(url_for('inscritos'))

    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        nuevo_correo = request.form['correo']
        nuevo_curso = request.form['curso']
        fecha_original = filas[registro_id][3]

        filas[registro_id] = [nuevo_nombre, nuevo_correo, nuevo_curso, fecha_original]

        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(encabezado)
            writer.writerows(filas)

        return redirect(url_for('inscritos'))

    registro = {
        'id': registro_id,
        'nombre': filas[registro_id][0],
        'correo': filas[registro_id][1],
        'curso': filas[registro_id][2],
        'fecha': filas[registro_id][3]
    }

    return render_template('editar.html', registro=registro)


if __name__ == '__main__':
    app.run(debug=True)