import slack
import os
import json
import uuid
import boto3
import datetime
import time
import requests
import decimal
import re
from flask import Flask, request, jsonify

SLACK_TOKEN = os.environ['SLACK_OAUTH']
BOT_TOKEN = os.environ['BOT_OAUTH']
client = slack.WebClient(token=SLACK_TOKEN)
botclient = slack.WebClient(token=BOT_TOKEN)

dynamodb = boto3.resource('dynamodb')
wagertable = dynamodb.Table('wagers')
wagerboard = dynamodb.Table('wagerboard')

app = Flask(__name__)

def challenging(content):
	try:
		username = content['user']['name']
		userid = content['user']['id']
		reporter = f"<@{userid}|{username}>"
		secondparty = content['submission']['secondparty']
		wagertext = content['submission']['wagertext']
		terms = content['submission']['terms']
		bettitle = content['submission']['bettitle']

		iconresponse = client.users_profile_get(user=userid)
		iconurl = iconresponse['profile']['image_512']
		iconname = iconresponse['profile']['real_name']
		challenged = client.users_profile_get(user=secondparty)
		challengedname = challenged['profile']['real_name']

		jsonstuff = [
			{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f'Hey {challengedname}, {reporter} is challenging you to a bet they\'re calling *"{bettitle}"*.',
			},
			"accessory": {
				"type": "image",
				"image_url": iconurl,
				"alt_text": reporter
				},
			},
			{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*The Bet*: \n{wagertext}"
				}
			},
			{
			"type": "divider"
			},
			{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*The Stakes*: \n{terms}"
				}
			},
			{
			"type": "actions",
			"elements": [
				{
					"type": "button",
					"style": "primary",
					"text": {
						"type": "plain_text",
						"text": "Accept",
						"emoji": True
					},
					"value": "accept%"+reporter+"%"+secondparty+"%"+bettitle
				},
				{
					"type": "button",
					"style": "danger",
					"text": {
						"type": "plain_text",
						"text": "Decline",
						"emoji": True
					},
					"value": "decline%"+reporter+"%"+secondparty+"%"+bettitle
					}
				]
			}	
				]
		client.chat_postMessage(channel=secondparty, blocks=jsonstuff)

	finally:
		pass

def bet_from_text(content):
	print("I AM IN BETFROMTEXT")
	trigger_id = content['trigger_id']
	print("TRIGGER ID IS")
	print(trigger_id)
	initial_bet = content['message']['text']
	initial_user = content['message']['user']

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
				"data_source": "users",
				"value": initial_user
			},
			{
				"type": "text",
				"label": "What's the bet?",
				"value": initial_bet,
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

def responding(content):
	challengedid = content['user']['id']
	challengedname = content['user']['username']
	channelid = content['channel']['id']
	timestamp = content['container']['message_ts']
	challenged = f"<@{challengedid}|{challengedname}>"
	determinerbase = content['actions'][0]['value']
	determiner = determinerbase.split("%")
	challenger = determiner[1]
	slackaddress = content['response_url']
	timesalt = time.localtime()
	time_string = time.strftime("%m%d%y%H%M%S", timesalt)

	req = requests.post(url = slackaddress, json = {'response_type': 'ephemeral','text': '','replace_original': True,'delete_original': True})

	bettitle = determiner[3]
	thebet = content['message']['blocks'][1]['text']['text']
	thebet = thebet.split(':')
	thebet = thebet[1].lstrip()
	thestakes = content['message']['blocks'][3]['text']['text']
	thestakes = thestakes.split(':')
	thestakes = thestakes[1].lstrip()

	if determiner[0] == 'accept':
		today = datetime.date.today()
		idnumber = time_string + challengedid[5] + challenger[3] + slackaddress[-3]

		newwager = [
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": ":rotating_light: *A NEW WAGER TO ANNOUNCE* :rotating_light:"
			}
		},
		{"type": "divider"},
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"{challenged} has agreed to wager terms with {challenger}"
			}
		},
		{"type": "divider"},
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*Title*: {bettitle}\n\n*The Bet*: {thebet}"
			}
		},
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*The Stakes*: {thestakes}"
			}
		}
		]

		wagertable.put_item(
			Item={
				'bettors': [challenger, challenged],
				'thebet': thebet,
				'thestakes': thestakes,
				'uuid': str(idnumber),
				'date': str(today),
				'title': bettitle,
				'resolved': False
			})
		client.chat_postMessage(channel="#botsbotsbots", blocks = newwager)

	elif determiner[0] == "decline":
		rejected = [
		{"type": "section",
			"text": { 
				"type": "mrkdwn",
				"text": f"{challenged} has rejected your proposal ({bettitle}. Be a better negotiator."}
		}	
		]

		challengersplit = challenger.split("|")
		challengerid = challengersplit[0].strip("<@>")
		print(f'ChallengerID is: {challengerid}')
		client.chat_postMessage(channel=challengerid, blocks = rejected)
	else:
		pass

def resolve_msg(content):
	response_url = content['response_url']
	user = content['user']['id']
	channel = content['channel']['id']
	wagernumber = content['submission']['whichwager']
	wager = wagertable.get_item(Key={'uuid': wagernumber})
	bettor1 = wager['Item']['bettors'][0]
	print("BETTOR1 IS "+ bettor1)
	bettor2 = wager['Item']['bettors'][1]
	print("BETTOR2 IS "+ bettor2)
	bettor1name = bettor1.split('|')
	bettor1name = bettor1name[1].rstrip('>')
	bettor2name = bettor2.split('|')
	bettor2name = bettor2name[1].rstrip('>')
	

	blockcontent = [
	{
		"type": "section",
		"text": {
			"type": "plain_text",
			"text": "Who won?",
			"emoji": True
				}
			},
				{
		"type": "actions",
		"elements": [
				{
				"type": "button",
				"text": {
					"type": "plain_text",
					"text": bettor1name,
					"emoji": True
				},
				"value": "fn%"+bettor1+"%"+bettor2+"%"+wagernumber
				},
            	{
				"type": "button",
				"text": {
					"type": "plain_text",
					"text": bettor2name,
					"emoji": True
							},
				"value": "fn%"+bettor2+"%"+bettor1+"%"+wagernumber
						}
					]
				}
			]
	client.chat_postEphemeral(channel = channel, user = user, blocks = blockcontent)

def resolve(content):
	slackaddress = content['response_url']
	requests.post(url = slackaddress, json = {'response_type': 'ephemeral','text': '','replace_original': True,'delete_original': True})
	print("IN RESOLVE")
	print(content)
	winnerchunk = content['actions'][0]['value']
	winnerchunk = winnerchunk.split('%')
	winner = winnerchunk[1]
	print("WINNER IS "+winner)
	winner = winner.strip("fn")
	loser = winnerchunk[2]
	print("LOSER IS "+loser)
	wagernumber = winnerchunk[3]

	try:
		wagerboard.put_item(
			Item={
			'slackname': winner,
			'bets': decimal.Decimal(1),
			},
			ConditionExpression='attribute_not_exists(slackname)')
	except:
		wagerboard.update_item(
			Key={'slackname': winner},
			UpdateExpression='set bets = bets + :val',
			ExpressionAttributeValues={
			':val': decimal.Decimal(1),
			},
			ReturnValues="UPDATED_NEW")

	wagertable.update_item(
		Key={'uuid': wagernumber},
		UpdateExpression='set resolved = :yup',
		ExpressionAttributeValues={
		':yup': True,
		},
		ReturnValues="UPDATED_NEW"
		)

	parsablereturn = wagertable.get_item(Key={'uuid': wagernumber})
	bettitle = parsablereturn['Item']['title']
	thebet = parsablereturn['Item']['thebet']
	thestakes = parsablereturn['Item']['thestakes']

	resolvedwager = [
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f":rotating_light: *{winner} has bested {loser} in a bet!* :rotating_light:"
			}
		},
		{"type": "divider"},
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*Title*: {bettitle}\n\n*The Bet*: {thebet}"
			}
		},
		{"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*The Stakes*: {thestakes}"
			}
		}
		]
	client.chat_postMessage(channel="#botsbotsbots", blocks = resolvedwager)

@app.route('/', methods=['POST'])
def lambda_handler():
	raw = request.form.get('payload')
	content = json.loads(raw)
	print(content)
	if content['type'] == "block_actions":
		deciderbag = content['actions']
		decider = deciderbag[0]['value']
		print(f'DECIDER IS {decider}')
		if decider[0] == "f":
			resolve(content)
		else:
			responding(content)
	elif content['type'] == "dialog_submission":
		if content['callback_id'] == "wager":
			challenging(content)
		elif content['callback_id'] == "resolve_dialog":
			resolve_msg(content)
		elif content['callback_id'] == "resolve_final":
			resolve(content)
		else:
			pass
	elif content['type'] == "message_action":
		bet_from_text(content)
	else:
		pass

	return '', 200

	