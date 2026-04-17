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

            for fila in reader:
                if len(fila) == 3:
                    registro = {
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


if __name__ == '__main__':
    app.run(debug=True)