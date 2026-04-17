from flask import Flask, render_template, request
import csv
import os

app = Flask(__name__)

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
        existe_archivo = os.path.isfile(archivo)

        with open(archivo, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)

            if not existe_archivo:
                writer.writerow(['Nombre', 'Correo', 'Curso'])

            writer.writerow([nombre, correo, curso])

        return render_template('gracias.html', nombre=nombre)

    return render_template('inscripcion.html')

if __name__ == '__main__':
    app.run(debug=True)