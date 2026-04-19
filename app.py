from flask import Flask, render_template, request, redirect, url_for, session, send_file
import os
import csv
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

from openpyxl import Workbook
from werkzeug.security import check_password_hash, generate_password_hash

import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")

DATABASE_URL = os.environ.get("DATABASE_URL")
SQLITE_DB = "femp.db"


def usar_postgres():
    return bool(DATABASE_URL)


def get_db_connection():
    if usar_postgres():
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            dbname=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            sslmode="require"
        )
        return conn
    else:
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        return conn


def get_cursor(conn):
    if usar_postgres():
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def fetchone_dict(cursor):
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)


def fetchall_dict(cursor):
    rows = cursor.fetchall()
    if usar_postgres():
        return [dict(r) for r in rows]
    return [dict(r) for r in rows]


def q(sql_postgres, sql_sqlite):
    return sql_postgres if usar_postgres() else sql_sqlite


def hoy_texto():
    return datetime.now().strftime('%d/%m/%Y %H:%M')


# =========================
# BASE DE DATOS
# =========================

def inicializar_db():
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(q("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre TEXT,
            usuario TEXT UNIQUE NOT NULL,
            correo TEXT,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operador',
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT
        )
    """, """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            usuario TEXT UNIQUE NOT NULL,
            correo TEXT,
            clave TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operador',
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT
        )
    """))

    cursor.execute(q("""
        CREATE TABLE IF NOT EXISTS inscritos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            correo TEXT NOT NULL,
            curso TEXT NOT NULL,
            fecha TEXT NOT NULL
        )
    """, """
        CREATE TABLE IF NOT EXISTS inscritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT NOT NULL,
            curso TEXT NOT NULL,
            fecha TEXT NOT NULL
        )
    """))

    conn.commit()
    cursor.close()
    conn.close()

    migrar_estructura_usuarios()
    crear_usuarios_base()


def migrar_estructura_usuarios():
    conn = get_db_connection()
    cursor = get_cursor(conn)

    if usar_postgres():
        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS nombre TEXT
        """)
        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS correo TEXT
        """)
        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS activo INTEGER NOT NULL DEFAULT 1
        """)
        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS fecha_creacion TEXT
        """)
    else:
        cursor.execute("PRAGMA table_info(usuarios)")
        columnas = [fila[1] for fila in cursor.fetchall()]

        if "nombre" not in columnas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN nombre TEXT")
        if "correo" not in columnas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN correo TEXT")
        if "activo" not in columnas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
        if "fecha_creacion" not in columnas:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN fecha_creacion TEXT")

    conn.commit()

    cursor.execute("SELECT id, usuario, rol, nombre, correo, fecha_creacion FROM usuarios")
    usuarios = fetchall_dict(cursor)

    for u in usuarios:
        nombre = u.get("nombre")
        correo = u.get("correo")
        fecha_creacion = u.get("fecha_creacion")

        if not nombre:
            nombre = u["usuario"]

        if not correo:
            correo = f'{u["usuario"]}@femp.local'

        if not fecha_creacion:
            fecha_creacion = hoy_texto()

        cursor.execute(
            q(
                "UPDATE usuarios SET nombre = %s, correo = %s, fecha_creacion = %s WHERE id = %s",
                "UPDATE usuarios SET nombre = ?, correo = ?, fecha_creacion = ? WHERE id = ?"
            ),
            (nombre, correo, fecha_creacion, u["id"])
        )

    conn.commit()
    cursor.close()
    conn.close()


def crear_usuarios_base():
    conn = get_db_connection()
    cursor = get_cursor(conn)

    usuarios_base = [
        {
            "nombre": "Administrador Principal",
            "usuario": "admin",
            "correo": "admin@femp.local",
            "clave": "098765",
            "rol": "admin"
        },
        {
            "nombre": "Operador Principal",
            "usuario": "operador",
            "correo": "operador@femp.local",
            "clave": "123456",
            "rol": "operador"
        },
        {
            "nombre": "Maestro Demo",
            "usuario": "maestro",
            "correo": "maestro@femp.local",
            "clave": "123456",
            "rol": "maestro"
        },
        {
            "nombre": "Estudiante Demo",
            "usuario": "estudiante",
            "correo": "estudiante@femp.local",
            "clave": "123456",
            "rol": "estudiante"
        }
    ]

    for u in usuarios_base:
        cursor.execute(
            q(
                "SELECT id FROM usuarios WHERE usuario = %s",
                "SELECT id FROM usuarios WHERE usuario = ?"
            ),
            (u["usuario"],)
        )
        existe = fetchone_dict(cursor)

        if not existe:
            cursor.execute(
                q(
                    """
                    INSERT INTO usuarios (nombre, usuario, correo, clave, rol, activo, fecha_creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    """
                    INSERT INTO usuarios (nombre, usuario, correo, clave, rol, activo, fecha_creacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    u["nombre"],
                    u["usuario"],
                    u["correo"],
                    generate_password_hash(u["clave"]),
                    u["rol"],
                    1,
                    hoy_texto()
                )
            )

    conn.commit()
    cursor.close()
    conn.close()


def migrar_csv_a_db():
    archivo_csv = "inscripciones.csv"

    if not os.path.isfile(archivo_csv):
        return

    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT COUNT(*) AS total FROM inscritos")
    total_row = fetchone_dict(cursor)
    total = total_row["total"] if total_row else 0

    if total > 0:
        cursor.close()
        conn.close()
        return

    with open(archivo_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)

        for fila in reader:
            if len(fila) == 4:
                cursor.execute(
                    q(
                        "INSERT INTO inscritos (nombre, correo, curso, fecha) VALUES (%s, %s, %s, %s)",
                        "INSERT INTO inscritos (nombre, correo, curso, fecha) VALUES (?, ?, ?, ?)"
                    ),
                    (fila[0], fila[1], fila[2], fila[3])
                )

    conn.commit()
    cursor.close()
    conn.close()


# =========================
# USUARIOS Y ROLES
# =========================

def obtener_usuario(usuario_ingresado):
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        q(
            "SELECT * FROM usuarios WHERE usuario = %s",
            "SELECT * FROM usuarios WHERE usuario = ?"
        ),
        (usuario_ingresado,)
    )

    usuario = fetchone_dict(cursor)
    cursor.close()
    conn.close()
    return usuario


def obtener_usuario_por_id(usuario_id):
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        q(
            "SELECT * FROM usuarios WHERE id = %s",
            "SELECT * FROM usuarios WHERE id = ?"
        ),
        (usuario_id,)
    )

    usuario = fetchone_dict(cursor)
    cursor.close()
    conn.close()
    return usuario


def listar_usuarios():
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute("SELECT * FROM usuarios ORDER BY id ASC")
    usuarios = fetchall_dict(cursor)

    cursor.close()
    conn.close()
    return usuarios


def crear_usuario(nombre, usuario, correo, clave, rol):
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        q(
            "SELECT id FROM usuarios WHERE usuario = %s OR correo = %s",
            "SELECT id FROM usuarios WHERE usuario = ? OR correo = ?"
        ),
        (usuario, correo)
    )
    existente = fetchone_dict(cursor)

    if existente:
        cursor.close()
        conn.close()
        return False, "El usuario o el correo ya existe."

    clave_hash = generate_password_hash(clave)

    cursor.execute(
        q(
            """
            INSERT INTO usuarios (nombre, usuario, correo, clave, rol, activo, fecha_creacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            """
            INSERT INTO usuarios (nombre, usuario, correo, clave, rol, activo, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        ),
        (nombre, usuario, correo, clave_hash, rol, 1, hoy_texto())
    )

    conn.commit()
    cursor.close()
    conn.close()
    return True, "Usuario creado correctamente."


def actualizar_usuario(usuario_id, nombre, usuario, correo, rol, activo):
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        q(
            "SELECT id FROM usuarios WHERE (usuario = %s OR correo = %s) AND id <> %s",
            "SELECT id FROM usuarios WHERE (usuario = ? OR correo = ?) AND id <> ?"
        ),
        (usuario, correo, usuario_id)
    )
    existente = fetchone_dict(cursor)

    if existente:
        cursor.close()
        conn.close()
        return False, "El usuario o el correo ya pertenece a otra cuenta."

    cursor.execute(
        q(
            """
            UPDATE usuarios
            SET nombre = %s, usuario = %s, correo = %s, rol = %s, activo = %s
            WHERE id = %s
            """,
            """
            UPDATE usuarios
            SET nombre = ?, usuario = ?, correo = ?, rol = ?, activo = ?
            WHERE id = ?
            """
        ),
        (nombre, usuario, correo, rol, activo, usuario_id)
    )

    conn.commit()
    cursor.close()
    conn.close()
    return True, "Usuario actualizado correctamente."


def cambiar_clave_usuario(usuario_id, nueva_clave):
    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        q(
            "UPDATE usuarios SET clave = %s WHERE id = %s",
            "UPDATE usuarios SET clave = ? WHERE id = ?"
        ),
        (generate_password_hash(nueva_clave), usuario_id)
    )

    conn.commit()
    cursor.close()
    conn.close()


def validar_usuario(usuario_ingresado, clave_ingresada):
    usuario = obtener_usuario(usuario_ingresado)
    if not usuario:
        return False

    if int(usuario.get("activo", 1)) != 1:
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


def es_admin():
    return session.get('rol') == 'admin'


def es_operador():
    return session.get('rol') == 'operador'


def es_maestro():
    return session.get('rol') == 'maestro'


def es_estudiante():
    return session.get('rol') == 'estudiante'


def es_admin_o_operador():
    return session.get('rol') in ['admin', 'operador']


# =========================
# NEGOCIO
# =========================

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


# =========================
# RUTAS PRINCIPALES
# =========================

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

        fecha = hoy_texto()

        conn = get_db_connection()
        cursor = get_cursor(conn)
        cursor.execute(
            q(
                "INSERT INTO inscritos (nombre, correo, curso, fecha) VALUES (%s, %s, %s, %s)",
                "INSERT INTO inscritos (nombre, correo, curso, fecha) VALUES (?, ?, ?, ?)"
            ),
            (nombre, correo, curso, fecha)
        )
        conn.commit()
        cursor.close()
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
            session['usuario'] = usuario_data['usuario']
            session['usuario_id'] = usuario_data['id']
            session['nombre'] = usuario_data.get('nombre', usuario_data['usuario'])
            session['rol'] = usuario_data['rol']
            return redirect(url_for('inscritos'))
        else:
            error = 'Usuario o contraseña incorrectos'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# =========================
# PANEL INSCRITOS
# =========================

@app.route('/inscritos')
def inscritos():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute("SELECT * FROM inscritos ORDER BY id ASC")
    filas = fetchall_dict(cursor)
    cursor.close()
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
    cursor = get_cursor(conn)
    cursor.execute("SELECT nombre, correo, curso, fecha FROM inscritos ORDER BY id ASC")
    filas = fetchall_dict(cursor)
    cursor.close()
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
    cursor = get_cursor(conn)
    cursor.execute("SELECT nombre, correo, curso, fecha FROM inscritos ORDER BY id ASC")
    filas = fetchall_dict(cursor)
    cursor.close()
    conn.close()

    archivo_excel = 'inscritos.xlsx'

    wb = Workbook()
    ws = wb.active
    ws.title = "Inscritos"
    ws.append(['Nombre', 'Correo', 'Curso', 'Fecha'])

    for fila in filas:
        ws.append([fila["nombre"], fila["correo"], fila["curso"], fila["fecha"]])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
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
    cursor = get_cursor(conn)
    cursor.execute(
        q(
            "DELETE FROM inscritos WHERE id = %s",
            "DELETE FROM inscritos WHERE id = ?"
        ),
        (registro_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('inscritos'))


@app.route('/editar-inscrito/<int:registro_id>', methods=['GET', 'POST'])
def editar_inscrito(registro_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    conn = get_db_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        q(
            "SELECT * FROM inscritos WHERE id = %s",
            "SELECT * FROM inscritos WHERE id = ?"
        ),
        (registro_id,)
    )
    fila = fetchone_dict(cursor)

    if not fila:
        cursor.close()
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
            cursor.close()
            conn.close()
            return render_template('editar.html', registro=registro, error='Todos los campos son obligatorios.')

        cursor.execute(
            q(
                "UPDATE inscritos SET nombre = %s, correo = %s, curso = %s WHERE id = %s",
                "UPDATE inscritos SET nombre = ?, correo = ?, curso = ? WHERE id = ?"
            ),
            (nuevo_nombre, nuevo_correo, nuevo_curso, registro_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('inscritos'))

    registro = {
        'id': fila["id"],
        'nombre': fila["nombre"],
        'correo': fila["correo"],
        'curso': fila["curso"],
        'fecha': fila["fecha"]
    }

    cursor.close()
    conn.close()
    return render_template('editar.html', registro=registro, error=None)


# =========================
# GESTION DE USUARIOS
# =========================

@app.route('/usuarios')
def usuarios():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    lista = listar_usuarios()
    return render_template(
        'usuarios.html',
        usuarios=lista,
        usuario_actual=session.get('usuario'),
        rol_actual=session.get('rol')
    )


@app.route('/crear-usuario', methods=['GET', 'POST'])
def crear_usuario_view():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    error = None
    exito = None

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        correo = request.form.get('correo', '').strip()
        clave = request.form.get('clave', '').strip()
        rol = request.form.get('rol', '').strip()

        roles_validos = ['admin', 'operador', 'maestro', 'estudiante']

        if not nombre or not usuario or not correo or not clave or rol not in roles_validos:
            error = 'Todos los campos son obligatorios y el rol debe ser válido.'
        else:
            ok, mensaje = crear_usuario(nombre, usuario, correo, clave, rol)
            if ok:
                exito = mensaje
            else:
                error = mensaje

    return render_template('crear_usuario.html', error=error, exito=exito)


@app.route('/editar-usuario/<int:usuario_id>', methods=['GET', 'POST'])
def editar_usuario_view(usuario_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    usuario_data = obtener_usuario_por_id(usuario_id)
    if not usuario_data:
        return redirect(url_for('usuarios'))

    error = None
    exito = None

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        correo = request.form.get('correo', '').strip()
        rol = request.form.get('rol', '').strip()
        activo = 1 if request.form.get('activo') == '1' else 0
        nueva_clave = request.form.get('clave', '').strip()

        roles_validos = ['admin', 'operador', 'maestro', 'estudiante']

        if not nombre or not usuario or not correo or rol not in roles_validos:
            error = 'Completa correctamente los campos.'
        else:
            ok, mensaje = actualizar_usuario(usuario_id, nombre, usuario, correo, rol, activo)
            if ok:
                if nueva_clave:
                    cambiar_clave_usuario(usuario_id, nueva_clave)
                exito = mensaje
                usuario_data = obtener_usuario_por_id(usuario_id)
            else:
                error = mensaje

    return render_template(
        'editar_usuario.html',
        usuario_data=usuario_data,
        error=error,
        exito=exito
    )


@app.route('/toggle-usuario/<int:usuario_id>', methods=['POST'])
def toggle_usuario(usuario_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    if not es_admin():
        return redirect(url_for('inscritos'))

    usuario_data = obtener_usuario_por_id(usuario_id)
    if not usuario_data:
        return redirect(url_for('usuarios'))

    nuevo_estado = 0 if int(usuario_data.get('activo', 1)) == 1 else 1

    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute(
        q(
            "UPDATE usuarios SET activo = %s WHERE id = %s",
            "UPDATE usuarios SET activo = ? WHERE id = ?"
        ),
        (nuevo_estado, usuario_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('usuarios'))


# =========================
# INICIO
# =========================

inicializar_db()
migrar_csv_a_db()

if __name__ == '__main__':
    app.run(debug=True)