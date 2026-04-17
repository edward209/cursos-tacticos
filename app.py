from flask import Flask, render_template, request, redirect, url_for, session, send_file
import csv
import os

app = Flask(__name__)
app.secret_key = 'clave_secreta_femp_2026'

USUARIO_PANEL = 'admin'
CLAVE_PANEL = '12345'


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

        archivo = 'inscripciones.csv'
        existe = os.path.isfile(archivo)

        with open(archivo, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if not existe:
                writer.writerow(['Nombre', 'Correo', 'Curso'])

            writer.writerow([nombre, correo, curso])

        return render_template('gracias.html', nombre=nombre)

    return render_template('inscripcion.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        usuario = request.form['usuario']
        clave = request.form['clave']

        if usuario == USUARIO_PANEL and clave == CLAVE_PANEL:
            session['logueado'] = True
            return redirect(url_for('inscritos'))
        else:
            error = 'Usuario o contraseña incorrectos'

    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logueado', None)
    return redirect(url_for('login'))


@app.route('/inscritos')
def inscritos():
    if not session.get('logueado'):
        return redirect(url_for('login'))

    registros = []
    archivo = 'inscripciones.csv'
    busqueda = request.args.get('q', '').strip().lower()

    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)

            for i, fila in enumerate(reader):
                if len(fila) == 3:
                    registro = {
                        'id': i,
                        'nombre': fila[0],
                        'correo': fila[1],
                        'curso': fila[2]
                    }

                    texto = f"{fila[0]} {fila[1]} {fila[2]}".lower()

                    if not busqueda or busqueda in texto:
                        registros.append(registro)

    return render_template(
        'inscritos.html',
        registros=registros,
        busqueda=busqueda
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


@app.route('/eliminar-inscrito/<int:registro_id>', methods=['POST'])
def eliminar_inscrito(registro_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    archivo = 'inscripciones.csv'
    filas = []

    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            encabezado = next(reader, None)

            for fila in reader:
                if len(fila) == 3:
                    filas.append(fila)

        if 0 <= registro_id < len(filas):
            filas.pop(registro_id)

        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            if encabezado:
                writer.writerow(encabezado)
            else:
                writer.writerow(['Nombre', 'Correo', 'Curso'])

            writer.writerows(filas)

    return redirect(url_for('inscritos'))


@app.route('/editar-inscrito/<int:registro_id>', methods=['GET', 'POST'])
def editar_inscrito(registro_id):
    if not session.get('logueado'):
        return redirect(url_for('login'))

    archivo = 'inscripciones.csv'
    filas = []
    encabezado = ['Nombre', 'Correo', 'Curso']

    if os.path.isfile(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            encabezado_archivo = next(reader, None)

            if encabezado_archivo:
                encabezado = encabezado_archivo

            for fila in reader:
                if len(fila) == 3:
                    filas.append(fila)

    if not (0 <= registro_id < len(filas)):
        return redirect(url_for('inscritos'))

    if request.method == 'POST':
        nuevo_nombre = request.form['nombre']
        nuevo_correo = request.form['correo']
        nuevo_curso = request.form['curso']

        filas[registro_id] = [nuevo_nombre, nuevo_correo, nuevo_curso]

        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(encabezado)
            writer.writerows(filas)

        return redirect(url_for('inscritos'))

    registro = {
        'id': registro_id,
        'nombre': filas[registro_id][0],
        'correo': filas[registro_id][1],
        'curso': filas[registro_id][2]
    }

    return render_template('editar.html', registro=registro)


if __name__ == '__main__':
    app.run(debug=True)