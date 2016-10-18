def supplement_list(request):
    context_dict = {}
    if 'shop_id' in request.session:
        shop_id = request.session['shop_id']
        shop = Shop.objects.get(id=shop_id,enable=1)
        try:
            supplement_list = Supplement.objects.filter(enable=1, customer__shop=shop).order_by('-id')
            i = 1
            new_supplement_list = []
            for supplement in supplement_list:
                try:
                    customer = Customer.objects.get(pk=supplement.customer_id)
                    context_dict['customer_name'] = customer.name
                except:
                    context_dict['customer_name'] = ''
                #supplement.shipping_date='123'
                res1 = Sale.objects.filter(supplement=supplement.id).order_by('shipping_date').first()
                try:
                    supplement.shipping_date=res1.shipping_date
                except:
                    supplement.shipping_date = ''

                res2 = Sale.objects.filter(supplement=supplement.id).order_by('billing_date').first()
                try:
                    supplement.billing_date = res2.billing_date
                except:
                    supplement.billing_date = ''

                res3 = Sale.objects.filter(supplement=supplement.id).count()
                if res3 !=0:
                    res4 = Sale.objects.filter(supplement=supplement.id,payment_date__isnull=True).count()
                    if res4 !=0:
                        supplement.payment_date='未'
                    else:
                        supplement.payment_date='済'
                else:
                    supplement.payment_date='未'
                #check supplement have supplement_sale
                supplement_sale_list = Sale.objects.filter(enable=1,supplement=supplement.id).count()
                supplement.sale_number = supplement_sale_list
                new_supplement_list.append([supplement, i])
                i += 1
            context_dict['supplement_list'] = new_supplement_list

            return render_to_response('supplement-list.html', RequestContext(request, context_dict))
        except OSError as e:
            messages_error = "errors message: %s" % e
            return render_to_response('404.html', \
                                      RequestContext(request, {'messages_error': messages_error}))
    else:
        return HttpResponseRedirect('/shops/')




@login_required
@user_passes_test(supplement_user_check,login_url='/alert/')
def shipping(request,shipping_number):
    if 'shop_id' in request.session:
        context_dict = {}
        shop_id = request.session['shop_id']
        shop_name = Shop.objects.get(pk= shop_id)
        list_supplement = request.GET['supplement_id']
        supplement_id_list = list_supplement.split(',')
        context_dict['supplement_id'] = list_supplement
        context_dict['shop_name'] = shop_name
        context_dict['shipping_number'] = shipping_number
        context_dict['edit'] = True
        if request.method == 'POST':
            try:
                shipping_form = ShippingForm(request.POST)
                if shipping_form.is_valid():
                    shipping_date = shipping_form.cleaned_data['shipping_date']
                    billing_date = shipping_form.cleaned_data['billing_date']
                    limit_date = shipping_form.cleaned_data['limit_date']
                    if shipping_date:
                        Sale.objects.filter(supplement__in=supplement_id_list).update(shipping_date=shipping_date)
                    if billing_date:
                        Sale.objects.filter(supplement__in=supplement_id_list).update(billing_date=billing_date)
                    if limit_date:
                        Sale.objects.filter(supplement__in=supplement_id_list).update(limit_date=limit_date)
                    for supplement_id in supplement_id_list:
                        supplement = Supplement.objects.get(pk=supplement_id)
                        lesson = Lesson.objects.filter(customer=supplement.customer_id).order_by('-id').first()
                        try:
                            if (lesson.frequency + lesson.free_frequency - lesson.use_frequency) == 0:
                                lesson.free_frequency = lesson.free_frequency +1
                                lesson.save()
                        except:
                            continue
                    return_dict = {}
                    return_dict['list_supplement'] = list_supplement
                    return HttpResponse(json.dumps(return_dict, ensure_ascii=False), \
                                        content_type='application/json')
                else:
                    context_dict['supplement_id'] = list_supplement
                    context_dict['shipping_form'] = shipping_form
                    return render_to_response('shipping.html', RequestContext(request,context_dict))
            except OSError as e:
                messages_error = "erros message: %s" % e
                return render_to_response('404.html', RequestContext(request, {'messages_error': messages_error}))
        else:
            shipping_form = ShippingForm()
            context_dict['shipping_form'] = shipping_form
            return render_to_response('shipping.html', RequestContext(request,context_dict))
        #return render_to_response('shipping.html',RequestContext(request, context_dict))
    else:
        return  HttpResponseRedirect('/shops/')
