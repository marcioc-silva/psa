from app import create_app

# Criamos a instância da aplicação através da função fábrica do __init__
app = create_app()

if __name__ == '__main__':
    print("-" * 30)
    print("SISTEMA PSA NESTLÉ ONLINE")
    print("-" * 30)
    print("Acesse no navegador: http://localhost:5000")
    
    # Rodando o servidor
    # host='0.0.0.0' permite que você acesse pelo celular na mesma rede Wi-Fi
    app.run(debug=True, host='0.0.0.0', port=5000)