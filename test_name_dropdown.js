id2valuebup = {};
id2callback = {};
Array.from($('div input[data-test-id="CustomTestName"]')).forEach(function(x, i) {
	id = x.getAttribute('id');
	name = x.getAttribute('name');
	id2valuebup[id] = x.value;
	$('#'+id).replaceWith('<select data-test-id="CustomTestName" id="'+id+'" name="'+name+'"><option value="Loading...">Loading...</option></select>');
	id2callback[id] = function(id2, items) {
		$('#'+id2).empty();
		Array.from(items).forEach(function(xx, ii) {
			if(xx == id2valuebup[id2]) {
				$('#'+id2).append('<option selected="yes" value="' + xx + '">' + xx + '</option>');
			} else {
				$('#'+id2).append('<option value="' + xx + '">' + xx + '</option>');
			}
			
		});

	};
});


// sources/examples/io_memory/test.cc

$.ajax('https://api.bitbucket.org/1.0/repositories/Niam/libdodo/directory', {
    'success': function(data, textStatus, oo) {
    	rv = ['Select a test'];
        data['values'].forEach(function(a) {
        	if(a.indexOf('.cc') >= 0) {
        		rv.push(a);
        	}
        });
        for(id in id2callback) {
        	id2callback[id](id, rv);
        }
    },
    'error': function(oo, textStatus, errorThrown) {
    	rv = [];
        var e = textStatus+': ' + errorThrown;
        e = e.replace('\n', ' ').replace('\r', ' ');
        rv.push(e);
        for(id in id2callback) {
        	id2callback[id](id, rv);
        }
    }
});
