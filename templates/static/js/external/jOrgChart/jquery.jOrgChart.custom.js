/**
 * jQuery org-chart/tree plugin.
 *
 * Author: Wes Nolte
 * http://twitter.com/wesnolte
 *
 * Based on the work of Mark Lee
 * http://www.capricasoftware.co.uk
 *
 * Copyright (c) 2011 Wesley Nolte
 * Dual licensed under the MIT and GPL licenses.
 *
 */
(function($) {


    $.fn.jOrgChart = function(options) {
        var opts = $.extend({}, $.fn.jOrgChart.defaults, options);
        var $appendTo = $(opts.chartElement);

        // build the tree
        $this = $(this);
        var $container = $("<div class='" + opts.chartClass + "'/>");
        if($this.is("ul")) {
            buildNode($this.find("li:first"), $container, 0, opts);
        }
        else if($this.is("li")) {
            buildNode($this, $container, 0, opts);
        }
        $appendTo.append($container);

        // add drag and drop if enabled
        if(opts.dragAndDrop){
            var $divNode = $('div.node:not(.temp)').not(".disabled");
            var $nodeParts = $divNode.not(".consumer_unit");
            var $nodeCU = $("div.node.consumer_unit");
            $divNode.draggable({
                cursor      : 'move',
                distance    : 40,
                helper      : 'clone',
                opacity     : 0.8,
                revert      : 'invalid',
                revertDuration : 100,
                snap        : 'div.node.expanded',
                snapMode    : 'inner',
                stack       : 'div.node'
            });

            $nodeParts.droppable({
                accept      : '.node',
                activeClass : 'drag-active',
                hoverClass  : 'drop-hover'
            });

            $nodeCU.droppable({
                accept      : '.consumer_unit',
                activeClass : 'drag-active',
                hoverClass  : 'drop-hover'
            });

            // Drag start event handler for nodes
            $divNode.bind("dragstart", function handleDragStart( event, ui ){

                var sourceNode = $(this);
                sourceNode.parentsUntil('.node-container')
                    .find('*')
                    .filter('.node')
                    .droppable('disable');
            });

            // Drag stop event handler for nodes
            $divNode.bind("dragstop", function handleDragStop( event, ui ){

                /* reload the plugin */
                $(opts.chartElement).children().remove();
                $this.jOrgChart(opts);
            });

            // Drop event handler for nodes
            $divNode.bind("drop", function handleDropEvent( event, ui ) {

                var targetID = $(this).data("tree-node");
                var targetLi = $this.find("li").filter(function() { return $(this).data("tree-node") === targetID; } );
                var targetUl = targetLi.children('ul');

                var sourceID = ui.draggable.data("tree-node");
                var sourceLi = $this.find("li").filter(function() { return $(this).data("tree-node") === sourceID; } );
                var sourceUl = sourceLi.parent('ul');

                if (targetUl.length > 0){
                    targetUl.append(sourceLi);
                } else {
                    targetLi.append("<ul></ul>");
                    targetLi.children('ul').append(sourceLi);
                }

                //Removes any empty lists
                if (sourceUl.children().length === 0){
                    sourceUl.remove();
                }

            }); // handleDropEvent

        } // Drag and drop
    };

    // Option defaults
    $.fn.jOrgChart.defaults = {
        chartElement : 'body',
        depth      : -1,
        chartClass : "jOrgChart",
        dragAndDrop: false
    };

    var nodeCount = 0;

    function removeNode($node, opts, $nodeDiv){
        if($nodeDiv.hasClass("temp")){
            if(click_flag){
                $node.remove();
                click_flag = true;
                $(opts.chartElement).children().remove();
                $this.jOrgChart(opts);
            }

        }
    }

    // Method that recursively builds the tree
    function buildNode($node, $appendTo, level, opts) {
        var $table = $("<table cellpadding='0' cellspacing='0' border='0'/>");
        var $tbody = $("<tbody/>");

        // Construct the node container(s)
        var $nodeRow = $("<tr/>").addClass("node-cells");
        var $nodeCell = $("<td/>").addClass("node-cell").attr("colspan", 2);
        var $childNodes = $node.children("ul:first").children("li");
        var $nodeDiv;

        if($childNodes.length > 1) {
            $nodeCell.attr("colspan", $childNodes.length * 2);
        }
        // Draw the node
        // Get the contents - any markup except li and ul allowed
        var $nodeContent = $node.clone()
            .children("ul,li")
            .remove()
            .end()
            .html();

        //Increaments the node count which is used to link the source list and the org chart
        nodeCount++;

        $node.data("tree-node", nodeCount);
        $nodeDiv = $("<div>").addClass("node")
            .data("tree-node", nodeCount)
            .append($nodeContent);


        $nodeDiv.append(
            "<div class='opciones hidden'>" +
            "</div>")
            .mouseenter(function(){
                $(this).find(".opciones").toggle();
            }).mouseleave(function(){
                $(this).find(".opciones").toggle();
            });

        var append_text = "<li class='temp'></li>";
        var $list_element = $node.clone()
            .children("ul,li")
            .remove()
            .end();
        // add temporal nodes

        if ($childNodes.length > 0) {
            if($node.find("ul:eq(0)").find("> li.temp").size()==0){
                $nodeDiv.mouseenter(function(){
                    if(!$list_element.hasClass("temp")){
                        $node.find("ul:eq(0)").append(append_text);
                        var classList = $node.attr('class').split(/\s+/);
                        $.each(classList, function(index,item) {
                           if(item != "virtual" && item != "consumer_unit"){
                               $node.find("ul:eq(0) li.temp").addClass(item);
                           }
                        });

                        $(opts.chartElement).children().remove();
                        $this.jOrgChart(opts);
                    }
                });
            }
        }else{

            $nodeDiv.mouseenter(function(){
                if(!$list_element.hasClass("temp")){
                    if($node.find("ul").size()==0){
                        append_text = "<ul>" + append_text + "</ul>";
                        $node.append(append_text);
                    }else{
                        $node.find("ul:eq(0)").append(append_text);
                    }
                    var classList = $node.attr('class').split(/\s+/);
                    $.each(classList, function(index,item) {
                        if(item != "virtual" && item != "consumer_unit"){
                            $node.find("ul:eq(0) li.temp").addClass(item);
                        }
                    });
                    $(opts.chartElement).children().remove();
                    $this.jOrgChart(opts);
                }
            });
        }
        $nodeDiv.mouseleave(function(){
            removeNode($node, opts, $nodeDiv);
        });

        $nodeCell.append($nodeDiv);
        $nodeRow.append($nodeCell);
        $tbody.append($nodeRow);

        if($childNodes.length > 0) {
            // if it can be expanded then change the cursor
            //$nodeDiv.css('cursor','n-resize');

            // recurse until leaves found (-1) or to the level specified
            if(opts.depth == -1 || (level+1 < opts.depth)) {
                var $downLineRow = $("<tr/>");
                var $downLineCell = $("<td/>").attr("colspan", $childNodes.length*2);
                $downLineRow.append($downLineCell);

                // draw the connecting line from the parent node to the horizontal line
                $downLine = $("<div></div>").addClass("line down");
                $downLineCell.append($downLine);
                $tbody.append($downLineRow);

                // Draw the horizontal lines
                var $linesRow = $("<tr/>");
                $childNodes.each(function() {
                    var $left = $("<td>&nbsp;</td>").addClass("line left top");
                    var $right = $("<td>&nbsp;</td>").addClass("line right top");
                    $linesRow.append($left).append($right);
                });

                // horizontal line shouldn't extend beyond the first and last child branches
                $linesRow.find("td:first")
                    .removeClass("top")
                    .end()
                    .find("td:last")
                    .removeClass("top");

                $tbody.append($linesRow);
                var $childNodesRow = $("<tr/>");
                $childNodes.each(function() {
                    var $td = $("<td class='node-container'/>");
                    $td.attr("colspan", 2);
                    // recurse through children lists and items
                    buildNode($(this), $td, level+1, opts);
                    $childNodesRow.append($td);
                });

            }
            $tbody.append($childNodesRow);
        }

        // any classes on the LI element get copied to the relevant node in the tree
        // apart from the special 'collapsed' class, which collapses the sub-tree at this point

        if ($node.attr('class') != undefined) {
            var classList = $node.attr('class').split(/\s+/);
            $.each(classList, function(index,item) {
                if (item == 'collapsed') {

                    $nodeRow.nextAll('tr').css('visibility', 'hidden');
                    $nodeRow.removeClass('expanded');
                    $nodeRow.addClass('contracted');
                    $nodeDiv.css('cursor','s-resize');
                } else {
                    $nodeDiv.addClass(item);
                }
            });
        }
        if(!$nodeDiv.hasClass("temp")){
            $nodeDiv.find(".opciones:eq(0)").append("<span class='edit'></span>");
            if($nodeDiv.hasClass("consumer_unit")){
                $nodeDiv.find(".opciones:eq(0)").append("<span class='del'></span>");
            }
        }else{
            $nodeDiv.find(".opciones:eq(0)").append("<span class='add' href='#fancy'></span><span class='del'></span>");
        }

        $table.append($tbody);
        $appendTo.append($table);

        /* Prevent trees collapsing if a link inside a node is clicked */
        $nodeDiv.children('a, span').click(function(e){
            e.stopPropagation();
        });
    }

})(jQuery);
