from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import sqlite3
import csv
from datetime import datetime
from openpyxl import Workbook
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")

DATABASE = "femp.db"


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operador'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inscritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT NOT NULL,
            curso TEXT NOT NULL,
            fecha TEXT NOT NULL
        )
    """)

    conn.commit()

    cursor.execute("SELECT COUNT(*) as total FROM usuarios")
    total = cursor.fetchone()["total"]

    if total == 0:
        cursor.execute(
            "INSERT INTO usuarios (usuario, clave, rol) VALUES (?, ?, ?)",
            ("admin", "098765", "admin")
        )
        cursor.execute(
            "INSERT INTO usuarios (usuario, clave, rol) VALUES (?, ?, ?)",
            ("operador", "123456", "operador")
        )
        conn.commit()

    conn.close()


def migrar_csv_a_sqlite():
    archivo_csv = 'inscripciones.csv'

    if not os.path.isfile(archivo_csv):
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM inscritos")
    total = cursor.fetchone()["total"]

    if total > 0:
        conn.close()
        return

    with open(archivo_csv, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)

        for fila in reader:
            if len(fila) == 4:
                cursor.execute(
                    "INSERT INTO inscritos (nombre, correo, curso, fecha) VALUES (?, ?, ?, ?)",
                    (fila[0], fila[1], fila[2], fila[3])
                )

    conn.commit()
    conn.close()

    print("✔ Datos migrados de CSV a SQLite")


def obtener_usuario(usuario_ingresado):
    conn = get_db_connection()
    usuario = conn.execute(
        "SELECT * FROM usuarios WHERE usuario = ?",
        (usuario_ingresado,)
    ).fetchone()
    conn.close()
    return usuario


def validar_usuario(usuario_ingresado, clave_ingresada):
    usuario = obtener_usuario(usuario_ingresado)
    if not usuario:
        return False

    clave_db = str(usuario["clave"]).strip()

    if clave_ingresada == clave_db:
        return True

    try:
        if check_password_hash(clave_db, clave_ingresada):
            return True
    except Exception:
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
    except Exception:
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
        nombre = request.form.get('nombre', '').strip()
        correo = request.form.get('correo', '').strip()
        curso = request.form.get('curso', '').strip()

        if not nombre or not correo or not curso:
            return render_template('inscripcion.html', error='Todos los campos son obligatorios.')

        fecha = datetime.now().strftime('%d/%m/%Y %H:%M')

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO inscritos (nombre, correo, curso, fecha) VALUES (?, ?, ?, ?)",
            (nombre, correo, curso, fecha)
        )
        conn.commit()
        conn.close()

        return render_template('gracias.html', nombre=nombre)

    return render_template('inscripcion.html', error=None)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        clave = request.form.get('clave', '').strip()

        if validar_usuario(usuario, clave):
            usuario_data = obtener_usuario(usuario)
            session['logueado'] = True
            session['usuario'] = usuario
            session['rol'] = usuario_data['rol']
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

    conn = get_db_connection()
    filas = conn.execute("SELECT * FROM inscritos ORDER BY id ASC").fetchall()
    conn.close()

    registros = []
    busqueda = request.args.get('q', '').strip().lower()
    area_filtro = request.args.get('area', '').strip()
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()

    fecha_desde_dt = None
    fecha_hasta_dt = None

    try:
        if fecha_desde:
            fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
    except Exception:
        fecha_desde_dt = None

    try:
        if fecha_hasta:
            fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d')
            fecha_hasta_dt = fecha_hasta_dt.replace(hour=23, minute=59, second=59)
    except Exception:
        fecha_hasta_dt = None

    for fila in filas:
        area = obtener_area(fila["curso"])
        fecha_registro_dt = convertir_fecha(fila["fecha"])

        registro = {
            'id': fila["id"],
            'nombre': fila["nombre"],
            'correo': fila["correo"],
            'curso': fila["curso"],
            'fecha': fila["fecha"],
            'area': area
        }

        texto = f"{fila['nombre']} {fila['correo']} {fila['curso']} {fila['fecha']} {area}".lower()

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

    conn = get_db_connection()
    filas = conn.execute("SELECT nombre, correo, curso, fecha FROM inscritos ORDER BY id ASC").fetchall()
    conn.close()

    archivo = 'inscripciones_exportadas.csv'

    with open(archivo, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Nombre', 'Correo', 'Curso', 'Fecha'])
        for fila in filas:
            writer.writerow([fila["nombre"], fila["correo"], fila["curso"], fila["fecha"]])

    return send_file(
        archivo,
        as_attachment=True,
        download_name='inscritos.csv'
    )


@app.route('/descargar-excel')
def descargar_excel():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    filas = conn.execute("SELECT nombre, correo, curso, fecha FROM inscritos ORDER BY id ASC").fetchall()
    conn.close()

    archivo_excel = 'inscritos.xlsx'

    wb = Workbook()
    ws = wb.active
    ws.title = "Inscritos"

    encabezados = ['Nombre', 'Correo', 'Curso', 'Fecha']
    ws.append(encabezados)

    for fila in filas:
        ws.append([fila["nombre"], fila["correo"], fila["curso"], fila["fecha"]])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except Exception:
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

    conn = get_db_connection()
    conn.execute("DELETE FROM inscritos WHERE id = ?", (registro_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('inscritos'))


@app.route('/editar-inscrito/<int:registro_id>', methods=['GET', 'POST'])
def editar_inscrito(registro_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    conn = get_db_connection()
    fila = conn.execute("SELECT * FROM inscritos WHERE id = ?", (registro_id,)).fetchone()

    if not fila:
        conn.close()
        return redirect(url_for('inscritos'))

    if request.method == 'POST':
        nuevo_nombre = request.form.get('nombre', '').strip()
        nuevo_correo = request.form.get('correo', '').strip()
        nuevo_curso = request.form.get('curso', '').strip()

        if not nuevo_nombre or not nuevo_correo or not nuevo_curso:
            registro = {
                'id': fila["id"],
                'nombre': fila["nombre"],
                'correo': fila["correo"],
                'curso': fila["curso"],
                'fecha': fila["fecha"]
            }
            conn.close()
            return render_template('editar.html', registro=registro, error='Todos los campos son obligatorios.')

        conn.execute(
            "UPDATE inscritos SET nombre = ?, correo = ?, curso = ? WHERE id = ?",
            (nuevo_nombre, nuevo_correo, nuevo_curso, registro_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('inscritos'))

    registro = {
        'id': fila["id"],
        'nombre': fila["nombre"],
        'correo': fila["correo"],
        'curso': fila["curso"],
        'fecha': fila["fecha"]
    }

    conn.close()
    return render_template('editar.html', registro=registro, error=None)


if __name__ == '__main__':
    inicializar_db()
    migrar_csv_a_sqlite()
    app.run(debug=True)
else:
    inicializar_db()
    migrar_csv_a_sqlite()
    