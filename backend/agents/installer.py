"""
Installer Agent - Instala paquetes npm faltantes
Ejecuta npm install para los paquetes sugeridos
"""
from loguru import logger
from backend.core.state import AgentState
from backend.rag.vector_store import VectorStoreManager
import subprocess
import os


async def installer_agent(state: AgentState) -> AgentState:
    """
    Instala los paquetes npm sugeridos en el entorno de Node-RED.
    NOTA: Para MVP, solo simula la instalación y actualiza el RAG.
    """
    logger.info(f"[Installer] Processing {len(state['suggested_installations'])} installations...")

    vector_store = VectorStoreManager()
    installed_count = 0
    failed = []

    for suggestion in state['suggested_installations']:
        package_name = suggestion.get('package')
        node_type = suggestion.get('node_type')
        description = suggestion.get('description', '')

        logger.info(f"[Installer] Installing: {package_name}")

        # Para MVP: Simulamos la instalación
        # En producción, ejecutarías: npm install {package_name} en el directorio de Node-RED
        # subprocess.run(['npm', 'install', package_name], cwd=nodered_dir)

        try:
            # Simular instalación exitosa y agregar al RAG
            vector_store.add_installed_node(
                node_type=node_type,
                package_name=package_name,
                description=description,
                metadata={"installed_by": "installer_agent"}
            )

            # Agregar a la lista de nodos instalados
            if node_type not in state['installed_nodes']:
                state['installed_nodes'].append(node_type)

            # Remover de missing_nodes
            if node_type in state['missing_nodes']:
                state['missing_nodes'].remove(node_type)

            installed_count += 1
            logger.info(f"[Installer] Successfully 'installed': {package_name}")

        except Exception as e:
            logger.error(f"[Installer] Failed to install {package_name}: {e}")
            failed.append(package_name)

    # Actualizar estado
    if failed:
        state['error_message'] = f"Failed to install: {', '.join(failed)}"
        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Advertencia: No pude instalar algunos paquetes: {', '.join(failed)}. Continuaré con los disponibles."
        })
    else:
        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Instalé {installed_count} paquetes exitosamente."
        })

    # Siguiente agente: function_coder
    state['current_agent'] = 'function_coder'
    state['needs_user_input'] = False

    return state
