# Methodo Respaldo - Sistema de Respaldo de Bases de Datos

## Versión 2.0 - Servicio Nativo de Windows

## Descripción
Sistema automatizado para realizar respaldos de bases de datos MySQL y SQL Server con soporte para servicio nativo de Windows usando pywin32.

### Características v2.0
- ✅ **Servicio Nativo de Windows**: Integración completa con el Service Control Manager (SCM)
- ✅ **Sin dependencias externas**: No requiere NSSM u otros wrappers
- ✅ **Arquitectura pywin32**: Usa ServiceFramework para comunicación directa con Windows
- ✅ **Doble modo**: Interfaz gráfica (GUI) y modo servicio en un solo ejecutable
- ✅ **Migración automática**: Detecta y migra instalaciones v1.0 (NSSM)
- ✅ **Logging mejorado**: Logs separados para aplicación y servicio
- ✅ **Recuperación automática**: Configuración de reintentos ante fallos

## Arquitectura Técnica

### Componentes Principales
- **main.py**: Punto de entrada con detección automática de modo (GUI/Servicio)
- **windows_service.py**: Implementación del servicio usando pywin32's ServiceFramework
- **StartServiceCtrlDispatcher**: Comunicación directa con SCM de Windows

### Requisitos del Sistema
- Windows 10/11 o Windows Server 2016+
- .NET Framework (para componentes de sistema)
- Permisos de Administrador (solo para instalación/desinstalación)

## Instalación

### Instalación Rápida
1. Descomprimir el paquete en el directorio deseado
2. Ejecutar `install_service.bat` **como Administrador**
3. El servicio se instalará y configurará automáticamente

### Instalación Manual
```cmd
# Instalar el servicio
MethodoRespaldo.exe --native-service install

# Configurar inicio automático con retardo
sc config MethodoRespaldo start= delayed-auto

# Iniciar el servicio
net start MethodoRespaldo
```

### Migración desde v1.0
El script `install_service.bat` detecta automáticamente instalaciones v1.0 (MethodoBackupService con NSSM) y:
1. Detiene y elimina el servicio v1.0
2. Preserva las configuraciones existentes
3. Instala el servicio v2.0 nativo

## Configuración
## Configuración

### Archivos de Configuración
- **server.json**: Configuración de conexión a base de datos y programación de backups
- **status.json**: Estado de la aplicación y última ejecución
- **db_config.json**: Configuración de conexión a base de datos
- **users.json**: Usuarios y credenciales de la aplicación

### Variables de Entorno (Embebidas en v2.0)
Las variables de entorno están embebidas en el ejecutable durante la compilación para mayor seguridad.

## Uso

### Modo Servicio (Recomendado)
El servicio se ejecuta automáticamente al iniciar Windows:
```cmd
# Verificar estado
sc query MethodoRespaldo

# Iniciar manualmente
net start MethodoRespaldo

# Detener
net stop MethodoRespaldo

# Ver logs
notepad logs\app.log
notepad logs\windows_service.log
```

### Modo GUI
Ejecutar `MethodoRespaldo.exe` directamente (doble clic):
- Iniciar sesión con las credenciales
- Configurar conexión a la base de datos
- Seleccionar directorio de respaldos
- Programar respaldos automáticos
- Monitorear estado de backups

### Comandos Útiles
```cmd
# Instalar servicio
install_service.bat

# Desinstalar servicio
uninstall_service.bat

# Verificar estado y configuración
verify_service.bat

# Probar conexión a base de datos
MethodoRespaldo.exe --test-connection
```

## Administración del Servicio

### Desde Windows Services (services.msc)
1. Abrir `services.msc`
2. Buscar "Methodo Respaldo - Sistema de Backups v2.0"
3. Clic derecho → Propiedades para configurar:
   - Tipo de inicio (Automático con retardo recomendado)
   - Cuenta de servicio
   - Recuperación ante fallos

### Desde Línea de Comandos
```cmd
# Ver configuración completa
sc qc MethodoRespaldo

# Ver estado actual
sc query MethodoRespaldo

# Configurar inicio automático con retardo
sc config MethodoRespaldo start= delayed-auto

# Configurar recuperación ante fallos
sc failure MethodoRespaldo reset= 86400 actions= restart/60000/restart/120000
```

## Logs y Diagnóstico

### Archivos de Log
- **logs/app.log**: Log principal de la aplicación (todos los eventos)
- **logs/windows_service.log**: Log específico del servicio de Windows
- **Windows Event Viewer**: System → Service Control Manager

### Troubleshooting Común

**Servicio no inicia:**
1. Verificar logs en `logs/app.log`
2. Revisar Event Viewer (Sistema → Service Control Manager)
3. Verificar permisos del directorio
4. Ejecutar `verify_service.bat` para diagnóstico

**Error de conexión a base de datos:**
1. Verificar credenciales en `server.json`
2. Probar conexión: `MethodoRespaldo.exe --test-connection`
3. Verificar firewall y conectividad de red

**Backups no se ejecutan:**
1. Verificar programación en `server.json`
2. Revisar logs para errores
3. Verificar permisos de escritura en directorio de destino

## Soporte

Para soporte técnico, contactar a:
- **Desarrollador**: Jose Jimenez
- **Email**: jose.jimenez@methodo.cl

## Versión
**2.0.0** - Octubre 2025
- Servicio nativo de Windows con pywin32
- Sin dependencia de NSSM
- Arquitectura StartServiceCtrlDispatcher
- Migración automática desde v1.0
- Logging mejorado y recuperación ante fallos

**1.0.0** - 2025 (Legacy)
- Servicio con NSSM wrapper

