import os
import random
import logging

from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Chargement des variables d'environnement ---
load_dotenv()

# --- Fonctions utilitaires ---
def load_system_prompt(filepath="prompts/system_prompt.txt"):
    """Charge le prompt système depuis un fichier."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Fichier de prompt système non trouvé: {filepath}")
        return None

def main():
    # --- Configuration du LLM ---
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        logger.error("La variable d'environnement GROQ_API_KEY n'est pas définie.")
        return

    model_name = os.getenv("MODEL_NAME", "llama-3.1-8b-instant")
    try:
        llm = ChatGroq(
            temperature=0.7,
            model_name=model_name,
            groq_api_key=groq_api_key
        )
        logger.info(f"Client Groq LLM '{llm.model_name}' initialisé.")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du LLM Groq: {e}")
        return

    # --- Initialisation de la conversation ---
    system_prompt_content = load_system_prompt()
    if not system_prompt_content:
        return

    # Liste de messages pour maintenir le contexte de la conversation (mémoire à court terme)
    messages = [SystemMessage(content=system_prompt_content)]

    initial_problem = input("Entrez le problème ou l'alerte à diagnostiquer : ")
    messages.append(HumanMessage(content=initial_problem))

    print("\n--- Début du Raisonnement de l'Agent ---")

    MAX_TURNS = 5 # Limite le nombre de tours pour éviter les boucles infinies

    for turn in range(MAX_TURNS):
        logger.info(f"Tour {turn + 1}/{MAX_TURNS}")
        try:
            # --- Étape 1: Le LLM raisonne et propose une Action ---
            response = llm.invoke(messages)
            logger.info(f"LLM a répondu. Ajouté à la mémoire.")
            messages.append(AIMessage(content=response.content))

            print(f"\n--- Réponse du LLM (Tour {turn + 1}) ---")
            print(response.content)
            print("---------------------------------")

            # --- Étape 2: Analyse de la Réponse du LLM pour l'Action ---
            if "DIAGNOSTIC TERMINE" in response.content:
                print("\nAgent a trouvé une réponse finale. Terminé.")
                break
            
            if "Action:" in response.content and "Thought:" in response.content:
                action_text_start = response.content.find("Action:") + len("Action:")
                action_text_end = response.content.find("Observation:")
                if action_text_end == -1:
                    action_text_end = len(response.content)

                simulated_action = response.content[action_text_start:action_text_end].strip()
                print(f"Agent a suggéré l'Action : '{simulated_action}'")

                # --- Étape 3: Simuler l'Observation de l'outil ---
                # C'est ici que nous injectons manuellement le "résultat de l'outil"
                # Dans les chapitres suivants, de vrais outils remplaceront cette simulation.
                if "PrometheusQueryTool" in simulated_action:
                    observation = "Observation: Résultat Prometheus: \n"

                    if "model_rmse_score" in simulated_action:
                        observation += "model_rmse_score est 28.5 (seuil critique 25.0).\n"
                    if "evidently_data_drift_detected_status" in simulated_action:
                        data_drift = 1
                        observation += f"evidently_data_drift_detected_status est {data_drift} (1 = dérive détectée).\n"
                    if "model_mape_score" in simulated_action:
                        observation += "model_mape_score est 35.2.\n"
                    if "model_rmse_score" not in simulated_action and "evidently_data_drift_detected_status" not in simulated_action and "model_mape_score" not in simulated_action:
                        observation += "Aucun résultat pour cette metrique.\n"

                elif "GrafanaDashboardTool" in simulated_action:
                    observation = "Observation: Résultat Grafana: Dashboard généré avec succès.\n"

                else:
                    observation = "Observation: Outil inconnu ou action non reconnue. Résultat simulé : 'OK'."
                
                print(f"Action exécutée. Observation simulée : '{observation}'")

                # --- Étape 4: Injecter l'Observation dans la mémoire de l'agent pour le prochain tour ---
                messages.append(HumanMessage(content=observation))
            else:
                print("Agent n'a pas suivi le format ReAct ou n'a pas proposé d'action. Terminé.")
                break

        except Exception as e:
            logger.error(f"Erreur lors du tour de l'agent: {e}")
            break
    
    print("\n--- Fin du Raisonnement de l'Agent ---")

if __name__ == "__main__":
    main()
