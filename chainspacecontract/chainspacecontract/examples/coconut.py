""" 
	CoCoNut smart contract.
"""


####################################################################
# imports
####################################################################
# general
from json import dumps, loads
from hashlib import sha256
# cypto
from petlib.bn import Bn
# chainspace
from chainspacecontract import ChainspaceContract
# coconut
from chainspacecontract.examples.coconut_util import pet_pack, pet_unpack, pack, unpackG1, unpackG2
from chainspacecontract.examples.coconut_lib import setup, mix_verify, prepare_mix_sign, verify_mix_sign

## contract name
contract = ChainspaceContract('coconut')


####################################################################
# methods
####################################################################
# ------------------------------------------------------------------
# init
# ------------------------------------------------------------------
@contract.method('init')
def init():
	return {
	    'outputs': (dumps({'type' : 'CoCoToken'}),),
	}

# ------------------------------------------------------------------
# create
# NOTE:
#   - sig is an aggregated sign on the hash of the instance object
# ------------------------------------------------------------------
@contract.method('create')
def create(inputs, reference_inputs, parameters, q, t, n, callback, vvk, sig):
    # pack sig and vvk
    packed_sig = (pack(sig[0]),pack(sig[1]))
    packed_vvk = (pack(vvk[0]),pack(vvk[1]),[pack(vvk[2][i]) for i in range(q)])

    # new petition object
    instance = {
        'type' : 'CoCoInstance',
        'q' : q,
        't' : t,
        'n' : n,
        'callback' : callback,
        'verifier' : packed_vvk
    }

    # return
    return {
        'outputs': (inputs[0], dumps(instance)),
        'extra_parameters' : (packed_sig,)
    }

# ------------------------------------------------------------------
# request_issue
# ------------------------------------------------------------------
@contract.method('request_issue')
def request_issue(inputs, reference_inputs, parameters, q, clear_m, hidden_m, pub):
    # execute PrepareMixSign
    params = setup(q)
    (cm, c, proof) = prepare_mix_sign(params, clear_m, hidden_m, pub)

    # new petition object
    issue_request = {
        'type' : 'CoCoRequest',
        'cm' : pack(cm),
        'c' : [(pack(ci[0]), pack(ci[1])) for ci in c]
    }

    # return
    return {
		'outputs': (inputs[0], dumps(issue_request)),
        'extra_parameters' : (pet_pack(proof), pack(pub))
	}

"""
# ------------------------------------------------------------------
# issue
# NOTE: 
#   - To be executed only by the first authority, the others have to
#     call 'add'.
# ------------------------------------------------------------------
@contract.method('issue')
def issue(inputs, reference_inputs, parameters, sk, vvk):
    (q, t, n, epoch) = parameters
    params = setup(q)

    # extract request
    issue_request = loads(inputs[0])
    cm = unpackG1(params, issue_request['cm'])
    c = [(unpackG1(params, issue_request['c'][0]), unpackG1(params, issue_request['c'][1]))]

    (h, enc_epsilon) = mix_sign(params, sk, cm, c, [epoch]) 
    packet = (pack(h), (pack(enc_epsilon[0]), pack(enc_epsilon[1])))

    # new petition object
    credential = {
        'type' : 'CoCoCredential',
        'sigs' : [packet]
    }

    # add vkk in parameters
    (g2, X, Y) = vvk
    packed_vvk = (pack(g2),pack(X),[pack(y) for y in Y])

    # return
    return {
        'outputs': (dumps(credential),),
        'extra_parameters' : (issue_request['cm'], issue_request['c'], packed_vvk),
    }

# ------------------------------------------------------------------
# add
# NOTE: 
#   - Updates the previous object to limit the numer of active obj.
# ------------------------------------------------------------------
@contract.method('add')
def add(inputs, reference_inputs, parameters, sk, packed_cm, packed_c, packed_vvk):
    (q, t, n, epoch) = parameters
    params = setup(q)

    # extract request
    old_credentials = loads(inputs[0])
    new_credentials = loads(inputs[0])
    cm = unpackG1(params, packed_cm)
    c = [(unpackG1(params, packed_c[0]), unpackG1(params, packed_c[1]))]

    # sign
    (h, enc_epsilon) = mix_sign(params, sk, cm, c, [epoch]) 
    
    # new petition object
    packet = (pack(h), (pack(enc_epsilon[0]), pack(enc_epsilon[1])))
    new_credentials['sigs'].append(packet)

    # return
    return {
        'outputs': (dumps(new_credentials),),
        'extra_parameters' : (packet, packed_cm, packed_c, packed_vvk)
    }

# ------------------------------------------------------------------
# spend
# NOTE: 
#   - this transaction should be used as callback for CSCoin.
# ------------------------------------------------------------------
@contract.method('spend')
def spend(inputs, reference_inputs, parameters, sig, ID, packed_vvk):
    (q, t, n, epoch) = parameters
    params = setup(q)

    # add ID to the list of spent ID
    new_ID_list = loads(inputs[0])
    new_ID_list['list'].append(pet_pack(ID))

    # pakc sig
    packed_sig = (pack(sig[0]), pack(sig[1]))
    
    # return
    return {
        'outputs': (dumps(new_ID_list),),
        'extra_parameters' : (pet_pack(ID), packed_sig, packed_vvk)
    }

"""

####################################################################
# checker
####################################################################
# ------------------------------------------------------------------
# check create
# ------------------------------------------------------------------
@contract.checker('create')
def create_checker(inputs, reference_inputs, parameters, outputs, returns, dependencies):
    try:
        # retrieve instance
        instance = loads(outputs[1])
        # retrieve parameters
        packed_sig = parameters[0]

        # check format
        if len(inputs) != 1 or len(reference_inputs) != 0 or len(outputs) != 2 or len(returns) != 0:
            return False 

        # check types
        if inputs[0] != outputs[0]: return False
        if instance['type'] != 'CoCoInstance': return False

        # check fields
        q = instance['q'] 
        t = instance['t'] 
        n = instance['n']
        instance['callback']
        packed_vvk = instance['verifier']
        if q < 1 or n < 1 or t > n: return False

        # verify signature
        params = setup(q)
        sig = (unpackG1(params, packed_sig[0]), unpackG1(params, packed_sig[1]))
        vvk = (unpackG2(params,packed_vvk[0]), unpackG2(params,packed_vvk[1]), [unpackG2(params,y) for y in packed_vvk[2]])
        hasher = sha256()
        hasher.update(outputs[1].encode('utf8'))
        m = Bn.from_binary(hasher.digest())
        if not mix_verify(params, vvk, None, sig, None, [m]): return False
   
        # otherwise
        return True

    except (KeyError, Exception):
        return False

# ------------------------------------------------------------------
# check request issue
# ------------------------------------------------------------------
@contract.checker('request_issue')
def request_issue_checker(inputs, reference_inputs, parameters, outputs, returns, dependencies):
    try:
        # retrieve instance
        instance = loads(outputs[0])
        request = loads(outputs[1])
        # retrieve parameters
        packed_proof = parameters[0]
        packed_pub = parameters[1]

        # check format
        if len(inputs) != 1 or len(reference_inputs) != 0 or len(outputs) != 2 or len(returns) != 0:
            return False 

        # check types
        if request['type'] != 'CoCoRequest': return False

        # check fields
        params = setup(instance['q'])
        cm = unpackG1(params, request['cm'])
        packed_c = request['c']
        c = [(unpackG1(params, ci[0]), unpackG1(params, ci[1])) for ci in packed_c]
        if inputs[0] != outputs[0]: return False

        # verify proof
        proof = pet_unpack(packed_proof)
        pub = unpackG1(params, packed_pub)
        if not verify_mix_sign(params, pub, c, cm, proof): return False

        ## TODO
        # verify depend transaction -- specified by 'callback'

        # otherwise
        return True

    except (KeyError, Exception):
        return False

# ------------------------------------------------------------------
# check request issue
# ------------------------------------------------------------------
"""
@contract.checker('request_issue')
def request_issue_checker(inputs, reference_inputs, parameters, outputs, returns, dependencies):
    try:
        # params
        (q, t, n, epoch) = parameters[0], parameters[1], parameters[2], parameters[3] 
        params = setup(q)

        # get objects
        issue_request = loads(outputs[1])
        cm = unpackG1(params, issue_request['cm'])
        c = [(unpackG1(params, issue_request['c'][0]), unpackG1(params, issue_request['c'][1]))]
        proof = tuple(pet_unpack(parameters[4]))
        pub = unpackG1(params, parameters[5])

        # check format
        if len(inputs) != 1 or len(reference_inputs) != 0 or len(outputs) != 2 or len(returns) != 0:
            return False 
        if len(parameters) != 6:
            return False

        # check types
        if loads(inputs[0])['type'] != 'CoCoToken' or loads(outputs[0])['type'] != 'CoCoToken':
            return False
        if issue_request['type'] != 'CoCoRequest':
            return False

        # verify proof
        if not verify_mix_sign(params, pub, c, cm, proof):
            return False

        ## TODO
        # verify depend transaction -- payment

        # otherwise
        return True

    except (KeyError, Exception):
        return False

# ------------------------------------------------------------------
# check issue
# ------------------------------------------------------------------
@contract.checker('issue')
def issue_checker(inputs, reference_inputs, parameters, outputs, returns, dependencies):
    try:
        # check format
        if len(inputs) != 1 or len(reference_inputs) != 0 or len(outputs) != 1 or len(returns) != 0:
            return False 
        if len(parameters) != 7:
            return False

        # check types
        if loads(inputs[0])['type'] != 'CoCoRequest' or loads(outputs[0])['type'] != 'CoCoCredential':
            return False

        # otherwise
        return True

    except (KeyError, Exception):
        return False

# ------------------------------------------------------------------
# check add
# ------------------------------------------------------------------
@contract.checker('add')
def add_checker(inputs, reference_inputs, parameters, outputs, returns, dependencies):
    try:
        # check format
        if len(inputs) != 1 or len(reference_inputs) != 0 or len(outputs) != 1 or len(returns) != 0:
            return False 
        if len(parameters) != 8:
            return False

        # check types
        if loads(inputs[0])['type'] != 'CoCoCredential' or loads(outputs[0])['type'] != 'CoCoCredential':
            return False

        # check list
        new_credentials = loads(outputs[0])
        old_credentials = loads(inputs[0])
        added_sig = parameters[4]
        if new_credentials['sigs'] != old_credentials['sigs'] + [added_sig]:
        	return False

        # otherwise
        return True

    except (KeyError, Exception):
        return False

# ------------------------------------------------------------------
# check spend
# ------------------------------------------------------------------
@contract.checker('spend')
def spend_checker(inputs, reference_inputs, parameters, outputs, returns, dependencies):
    try:
    	
        # check format
        if len(inputs) != 1 or len(reference_inputs) != 0 or len(outputs) != 1 or len(returns) != 0:
            return False 
        if len(parameters) != 7:
            return False

        # check types
        if loads(inputs[0])['type'] != 'CoCoList' or loads(outputs[0])['type'] != 'CoCoList':
            return False
   
    	# get parameters
        (q, t, n, epoch) = parameters[0], parameters[1], parameters[2], parameters[3] 
    	old_ID_list = loads(inputs[0])['list']
    	new_ID_list = loads(outputs[0])['list']
        packed_ID = parameters[4]
        ID = pet_unpack(packed_ID)
        packed_vvk = parameters[6]
    	
        ## verify sign
        params = setup(q)
        (G, o, g1, hs, g2, e) = params
        sig = (unpackG1(params,parameters[5][0]), unpackG1(params,parameters[5][1]))
        vvk = (unpackG2(params,packed_vvk[0]), unpackG2(params,packed_vvk[1]), [unpackG2(params,y) for y in packed_vvk[2]])
        (g2, X, Y) = vvk
        (h, epsilon) = sig
        assert not h.isinf() and e(h, X + ID*Y[0] + epoch*Y[1]) == e(epsilon, g2) 

        # check ID has not been spent
        if ID in old_ID_list:
        	return False

    	if new_ID_list != old_ID_list + [packed_ID]:
    		return False

        # otherwise
        return True

    except (KeyError, Exception):
        return False
"""

####################################################################
# main
####################################################################
if __name__ == '__main__':
    contract.run()



####################################################################