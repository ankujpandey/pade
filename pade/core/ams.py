# -*- coding: utf-8 -*-

# Framework para Desenvolvimento de Agentes Inteligentes KajuPy

# Copyright (C) 2014  Lucas Silveira Melo

# Este arquivo é parte do programa KajuPy
#
# KajuPy é um software livre; você pode redistribuí-lo e/ou 
# modificá-lo dentro dos termos da Licença Pública Geral GNU como 
# publicada pela Fundação do Software Livre (FSF); na versão 3 da 
# Licença, ou (na sua opinião) qualquer versão.
#
# Este programa é distribuído na esperança de que possa ser  útil, 
# mas SEM NENHUMA GARANTIA; sem uma garantia implícita de ADEQUAÇÃO a qualquer
# MERCADO ou APLICAÇÃO EM PARTICULAR. Veja a
# Licença Pública Geral GNU para maiores detalhes.
#
# Você deve ter recebido uma cópia da Licença Pública Geral GNU
# junto com este programa, se não, escreva para a Fundação do Software
# Livre(FSF) Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA


from twisted.internet import protocol, reactor
from twisted.enterprise import adbapi
from pickle import dumps, loads
from uuid import uuid4

from pade.core.peer import PeerProtocol

from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.misc.utility import display_message


class AgentManagementProtocol(PeerProtocol):

    """
        Agent Management protocol
        -------------------------

        Esta classe implementa os comportamentos de um agente AMS

        A princiapal funcionalidade do AMS é registrar todos os agentes que
        estão conectados ao sistema e atualizar a tabela de agentes de cada
        um deles sempre que um novo agente se conectar.
    """

    def __init__(self, fact):
        """
            Este método Inicializa o objeto que implementa a classe AMS

            Parâmetros
            ----------
            fact: fact do protocolo do AMS
        """
        PeerProtocol.__init__(self, fact)

    def connectionMade(self):
        """
            connectionMade
            --------------

            Este método é executado sempre que uma conexão é realizada
            com o agente AMS
        """
        # armazena as informações do agente conectado por meio do metodo
        # transport.getPeer()
        peer = self.transport.getPeer()

        # laço for percorre as mensagens armazenadas na variavel
        # fact.messages e caso alguma mensagem seja para o agente
        # conectado esta será enviada
        for message in self.fact.messages:
            if int(message[0].port) == int(peer.port):
                # envia a mensagem por meio do metodo sendLine()
                self.send_message(message[1].get_message())
                # remove a mesagem enviada da variavel fact.messages
                self.fact.messages.remove(message)
                display_message(
                    self.fact.aid.name,
                    'Mensagem enviada ao agente ' + message[0].name)
                break

    def connectionLost(self, reason):
        """
            connectionLost
            --------------

            Este método é executado sempre que uma conexão é perdida
            com o agente AMS
        """
        if self.message is not None:
            message = PeerProtocol.connectionLost(self, reason)

            # como o agente AMS só recebe mensagens
            self.handle_identif(loads(message.content))
            self.message = None

    def send_message(self, message):
        PeerProtocol.send_message(self, message)

    def connection_test_send(self):
        """
            Este método é executado ciclicamente com o objetivo de
            verificar se os agentes estão conectados
        """
        if self.fact.debug:
            display_message(self.fact.aid.name,
                            'Enviando mensagens de verificação da conexão...')
        for name, aid in self.fact.table.iteritems():
            if self.fact.debug:
                display_message(
                    self.fact.aid.name,
                    'Tentando conexão com agente ' + name + '...')
            reactor.connectTCP(
                aid.host, int(aid.port), self.fact)
            self.transport.loseConnection()
        else:
            reactor.callLater(1,
                              self.connection_test_send)

    def lineReceived(self, line):
        """
            Quando uma mensagem é enviada ao AMS este método é executado.
            Quando em fase de identificação, o AMS registra o agente
            em sua tabele de agentes ativos
        """

        # recebe uma parte da mensagem enviada
        PeerProtocol.lineReceived(self, line)

    def handle_identif(self, aid):
        """
            handle_identif
            --------------

            Este método é utilizado para cadastrar o agente que esta se identificando
            na tabela de agentes ativos.
        """
        if aid.name in self.fact.table:
            display_message(
                'AMS', 'Falha na Identificacao do agente ' + aid.name)

            # prepara mensagem de resposta
            message = ACLMessage(ACLMessage.REFUSE)
            message.set_sender(self.fact.aid)
            message.add_receiver(aid)
            message.set_content(
                'Ja existe um agente com este identificador. Por favor, escolha outro.')
            # envia mensagem
            self.send_message(message.get_message())
            return
        self.aid = aid
        self.fact.table[self.aid.name] = self.aid
        display_message(
            'AMS', 'Agente ' + aid.name + ' identificado com sucesso')

        # prepara mensagem de resposta
        message = ACLMessage(ACLMessage.INFORM)
        message.set_sender(self.fact.aid)
        for receiver in self.fact.table.values():
            message.add_receiver(receiver)

        message.set_content(dumps(self.fact.table))
        self.broadcast_message(message)

        # envia tabela de agentes atualizada a todos os agentes com conexao
        # ativa com o AMS

    def broadcast_message(self, message):
        """
            broadcast_message
            -----------------

            Este método é utilizado para o envio de mensagems de atualização da
            tabela de agentes ativos sempre que um novo agente é connectado.
        """
        for name, aid in self.fact.table.iteritems():
            reactor.connectTCP(
                aid.host, int(aid.port), self.fact)
            self.fact.messages.append((aid, message))


class AgentManagementFactory(protocol.ClientFactory):

    """
        AgentManagementFactory
        ----------

        Esta classe implementa as ações e atributos do protocolo AMS
        sua principal função é armazenar informações importantes ao protocolo de comunicação 
        do agente AMS
    """

    def __init__(self, port, debug):

        self.state = 'IDENT'
        self.debug = debug
        # dictionary que tem como keys o nome dos agentes e como valor o objeto aid que identifica o agente
        # indicado pela chave
        self.table = {}

        # lista que armazena as mensagens recebidas pelo AMS, devera ser utilizada posteriormente pelo
        # serviço de visualização de mensagens
        self.messages = []

        # aid do agente AMS
        self.aid = AID(name='AMS' + '@' + 'localhost' + ':' + str(port))

        display_message(
            'AMS', 'AMS esta servindo na porta' + str(self.aid.port))

        # instancia do objeto que implementa o protocolo AMS
        self.protocol = AgentManagementProtocol(self)

        # instancia o objeto que realizará a conexão com o banco de dados
        self.conn = adbapi.ConnectionPool(
            'sqlite3', 'database.db', check_same_thread=False)
        self.d = self.createAgentsTable()
        self.d.addCallback(self.insert_agent)

    def buildProtocol(self, addr):
        return self.protocol

    def clientConnectionFailed(self, connector, reason):
        for name, aid in self.table.iteritems():
            if aid.port == connector.port:
                display_message(
                    self.aid.name, 'O agente ' + aid.name + ' esta desconectado.')
                print reason
                self.table.pop(name)
                message = ACLMessage(ACLMessage.INFORM)
                message.set_sender(self.aid)
                message.set_content(dumps(self.table))
                self.protocol.broadcast_message(message)
                break

    # =======================================================================
    # Estes métodos são utilizados para a comunicação do loop
    # twisted com o banco de dados
    # =======================================================================
    def createAgentsTable(self):
        display_message(
            self.aid.name, 'Tabela de agentes criada no banco de dados.')
        return self.conn.runInteraction(self._cretateAgentsTable)

    def _cretateAgentsTable(self, transaction):
        display_message(
            self.aid.name, 'Tabela de agentes criada no banco de dados.')
        self.dbid = 'agents_' + str(uuid4().time)
        s = 'CREATE TABLE ' + self.dbid + '( id INTEGER PRIMARY KEY AUTOINCREMENT, ' +\
            'name VARCHAR(20), ' +\
            'port INTEGER);'
        transaction.execute(s)
        #transaction.execute('INSERT INTO ' + self.dbid + ' VALUES ' + '')

    def insert_agent(self):
        pass