#!/usr/bin/python
import ConfigParser
import time
import sys
import os
import numpy as np
import pdb
import theanets
import climate
import theano as T
import random

logging = climate.get_logger(__name__)

climate.enable_default_logging()

def load_vocab(vocab_fn):
    w2ix = {}
    ix2w = {}

    with open(vocab_fn,'r') as fid:
        for idx, aline in enumerate(fid):
            w = aline.strip()
            w2ix[w] = idx
            ix2w[idx] = w
    return w2ix, ix2w

def load_split(w2ix, split_fn):
    max_seq_len = 0
    line_num = 0
    with open(split_fn, 'r') as fid:
        for aline in fid:
            toks = aline.strip().split()
            max_seq_len = max(max_seq_len, len(toks))
            line_num +=1

    np_split = np.zeros((line_num, max_seq_len), dtype = 'int32')
    np_split[:] = -1

    with open(split_fn,'r') as fid:
        for row, aline in enumerate(fid):
            toks = aline.strip().split()
            col = 0
            for tok in toks:
                if tok in w2ix:
                    np_split[row, col] = w2ix[tok]
                    col += 1
    return np_split
            
if __name__ == '__main__':

    cf = ConfigParser.ConfigParser()
    if len(sys.argv) < 2:
        logging.info('Usage: %s <conf_fn>',sys.argv[0])
        sys.exit()

    cf.read(sys.argv[1])
    h_size=int(cf.get('INPUT','h_size'))
    e_size=int(cf.get('INPUT','e_size'))
    h_l1=float(cf.get('INPUT','h_l1'))
    h_l2=float(cf.get('INPUT','h_l2'))
    l1=float(cf.get('INPUT','l1'))
    l2=float(cf.get('INPUT','l2'))
    model_fn = cf.get('INPUT', 'model_fn')
    batch_size = int(cf.get('INPUT', 'batch_size'))

    src_vocab_fn = cf.get('INPUT', 'src_vocab_fn')
    src_train_fn = cf.get('INPUT', 'src_train_fn')
    src_val_fn = cf.get('INPUT', 'src_val_fn')

    dst_vocab_fn = cf.get('INPUT', 'dst_vocab_fn')
    dst_train_fn = cf.get('INPUT', 'dst_train_fn')
    dst_val_fn = cf.get('INPUT', 'dst_val_fn')

    dropout = float(cf.get('INPUT', 'dropout'))

    save_dir=cf.get('OUTPUT', 'save_dir')

    # NOw, we can load the vocab and the fea.
    src_w2ix, src_ix2w = load_vocab(src_vocab_fn)
    dst_w2ix, dst_ix2w = load_vocab(dst_vocab_fn)

    src_train_np = load_split(src_w2ix, src_train_fn)
    src_val_np = load_split(src_w2ix, src_val_fn)
    

    dst_train_np = load_split(dst_w2ix, dst_train_fn)
    dst_val_np = load_split(dst_w2ix, dst_val_fn)

    train_range = range(src_train_np.shape[0])
    def batch_train():
        random.shuffle(train_range)

        src = np.zeros((src_train_np.shape[1], batch_size, len(src_w2ix)), dtype = 'int32')
        src_mask = np.zeros((src_train_np.shape[1], batch_size, len(src_w2ix)), dtype = 'int32')

        dst = np.zeros((dst_train_np.shape[1], batch_size, len(dst_w2ix)), dtype = 'int32')
        dst_mask = np.zeros((dst_train_np.shape[1], batch_size, len(dst_w2ix)), dtype = 'int32')

        for i in range(batch_size):
            src_i = src_train_np[train_range[i],:]
            for j,pos in enumerate(src_i):
                src[j, i, pos] = 1
                src_mask[j, i] = 1

        for i in range(batch_size):
            dst_i = dst_train_np[train_range[i],:]
            for j,pos in enumerate(dst_i):
                dst[j, i, pos] = 1
                dst_mask[j, i] = 1
        return src, src_mask, dst, dst_mask

    val_range = range(src_val_np.shape[0])
    def batch_val():
        random.shuffle(val_range)

        src = np.zeros((src_val_np.shape[1], batch_size, len(src_w2ix)), dtype = 'int32')
        src_mask = np.zeros((src_val_np.shape[1], batch_size, len(src_w2ix)), dtype = 'int32')

        dst = np.zeros((dst_val_np.shape[1], batch_size, len(dst_w2ix)), dtype = 'int32')
        dst_mask = np.zeros((dst_val_np.shape[1], batch_size, len(dst_w2ix)), dtype = 'int32')

        for i in range(batch_size):
            src_i = src_val_np[val_range[i],:]
            for j,pos in enumerate(src_i):
                src[j, i, pos] = 1
                src_mask[j, i] = 1

        for i in range(batch_size):
            dst_i = dst_val_np[val_range[i],:]
            for j,pos in enumerate(dst_i):
                dst[j, i, pos] = 1
                dst_mask[j, i] = 1
        return src, src_mask, dst, dst_mask

    def layer_input_encdec(src_size, dst_size, emb_size):
        return dict(src_size = src_size, dst_size = dst_size, emb_size = emb_size)

    def layer_lstm(n):
        return dict(form = 'lstm', size = n)

    if not os.path.isdir(save_dir):
        os.makedirs(save_dir)

    time_str = time.strftime("%d-%b-%Y-%H%M%S", time.gmtime())
    save_prefix = os.path.join(save_dir, os.path.splitext(os.path.basename(sys.argv[1]))[0])
    save_fn = save_prefix + '_' + time_str + '.pkl'
    logging.info('will save model to %s', save_fn)
    
    if os.path.isfile(model_fn):
        e = theanets.Experiment(model_fn)
    else:
        pdb.set_trace()
        e = theanets.Experiment(
            theanets.recurrent.Classifier,
            layers=(layer_input_encdec(len(src_w2ix), len(dst_w2ix), e_size),
            #layers=(32,
            layer_lstm(h_size),
            (len(dst_w2ix), 'softmax')),
            weighted=True,
            encdec = True
        )
        e.train(
            batch_train,
            batch_val,
            algorithm='rmsprop',
            learning_rate=0.0001,
            momentum=0.9,
            max_gradient_clip=10,
            input_noise=0.0,
            train_batches=30,
            valid_batches=3,
            hidden_l1 = h_l1,
            hidden_l2 = h_l2,
            weight_l1 = l1,
            weight_l2 = l2,
            batch_size=batch_size,
            dropout=dropout,
            save_every = 100
        )

    e.save(save_fn)