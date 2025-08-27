import os
import logging

from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Chargement des variables d'environnement ---
load_dotenv()

def main():
    # --- 1. Récupération de la clé API Groq ---
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("La variable d'environnement GROQ_API_KEY n'est pas définie. Veuillez la configurer dans le fichier .env.")
        return

    # --- 2. Initialisation du client Groq LLM ---
    try:
        # Nous initialisons ChatGroq avec le modèle que nous utiliserons tout au long du cours.
        llm = ChatGroq(
            temperature=0.7, # contrôle la créativité du modèle (0.0 très factuel, 1.0 très créatif).
            model_name="llama-3.1-8b-instant", # Le modèle Groq recommandé pour ce cours
            groq_api_key=groq_api_key
        )
        logger.info(f"Client Groq LLM '{llm.model_name}' initialisé avec succès.")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du LLM Groq: {e}")
        return

    # --- 3. Définition des messages à envoyer au LLM ---
    # Un "SystemMessage" donne des instructions générales ou une persona au LLM.
    # Un "HumanMessage" est le prompt de l'utilisateur.
    messages = [
        SystemMessage(content="Tu es un assistant IA utile et concis, expert en MLOps."),
        HumanMessage(content="Explique ce qu'est un agent IA en une seule phrase.")
    ]

    # --- 4. Invocation du LLM et affichage de la réponse ---
    logger.info("Envoi du prompt au LLM...")
    try:
        response = llm.invoke(messages) # Interroge notre llm avec notre message comme prompt.
        logger.info("Réponse du LLM reçue.")
        print("\n--- Réponse du LLM ---")
        print(response.content)
        print("--------------------")
    except Exception as e:
        logger.error(f"Erreur lors de l'invocation du LLM: {e}")

if __name__ == "__main__":
    main()