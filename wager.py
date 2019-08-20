import slack
import os
import json
import uuid
import boto3
import datetime
from flask import Flask, request

SLACK_TOKEN = os.environ['SLACK_OAUTH']
client = slack.WebClient(token=SLACK_TOKEN)
dynamodb = boto3.resource('dynamodb')
wagertable = dynamodb.Table('wagers')
wagerboard = dynamodb.Table('wagerboard')

app = Flask(__name__)

def listwagers():
	response_person = request.form.get('user_id')
	channel = request.form.get('channel_id')
	rows = wagertable.scan(
			ProjectionExpression="bettors, thebet, thestakes, #d, resolved",
			ExpressionAttributeNames= {'#d':'date'},
			)
	betlistblocks = [{"type": "section","text": {"type": "mrkdwn","text": "*The following bets remain undecided.*\n"}},{"type": "divider"}]
	for entry in rows['Items']:
		if entry['resolved'] == True:
			pass
		else:
			bettor1 = entry['bettors'][0]
			bettor2 = entry['bettors'][1]
			thebet = entry['thebet']
			thestakes = entry['thestakes']
			betdate = entry['date']
			betjson = [
				{"type": "section",
					"text": {
						"type": "mrkdwn",
						"text": f"{bettor1} *and* {bettor2} *bet that:* {thebet} \n:wavy_dash::wavy_dash::wavy_dash:\n*The Stakes*: {thestakes}"
							}

				},
				{
					"type": "context",
					"elements": [
								{
						"type": "mrkdwn",
						"text": f"on {betdate}"
								}
							]
				},
				{
				"type": "divider"
				},				
				{
				"type": "divider"
				},
				]
			betlistblocks.append(betjson[0])
			betlistblocks.append(betjson[1])
			betlistblocks.append(betjson[2])
			betlistblocks.append(betjson[3])

	client.chat_postEphemeral(channel = channel, user = response_person, blocks = betlistblocks)

def firstdialog():
	trigger_id = request.form.get('trigger_id')

	dialogcontent = {
			"callback_id": "wager",
			"title": "Gravelbetting",
			"submit_label": "Propose",
			"notify_on_cancel": False,
			"elements": [
			{
				"type": "select",
				"label": "Who do you want to bet with",
				"name": "secondparty",
				"data_source": "users"
			},
			{
				"type": "text",
				"label": "What's the bet?",
				"name": "wagertext"
			},
			{	"type": "text",
				"label": "What are the stakes?",
				"placeholder": "If Adam wins, Bethany owes him a car. If Bethany wins, Adam gets a cocktail.",
				"name": "terms"
			},
			{
				"type": "text",
				"label": "Give this bet a short title",
				"name": "bettitle"
			}
			]
			}

	client.dialog_open(dialog=dialogcontent,trigger_id=trigger_id)

def resolve():
	trigger_id = request.form.get('trigger_id')
	dialogcontent = {
			"callback_id": "resolve_dialog",
			"title": "Resolve a Gravelbet",
			"submit_label": "Resolve",
			"notify_on_cancel": False,
			"elements": [
			{
				"type": "select",
				"label": "Which wager do you want to resolve?",
				"name": "whichwager",
				"data_source": "external"
			},
			]
			}

	client.dialog_open(dialog=dialogcontent,trigger_id=trigger_id)

@app.route('/', methods=['POST'])
def lambda_handler():
	text = request.form.get('text')
	
	if text == 'list':
		listwagers()
		return '', 200
	elif text == 'resolve':
		resolve()
		return '', 200
	else:
		try:
			firstdialog()
		except:
			return "Whoops. Something went wrong. Tell Genghis what you tried to do and he'll tell you if you're an idiot"
		finally:
			return '', 200